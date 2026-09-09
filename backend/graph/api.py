from typing import Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from neo4j import Driver

from graph import service
from graph import schemas
from graph.neo4j_client import create_driver

_driver_cache: Optional[Driver] = None

_WALLET_PATTERN = r"^[a-z0-9]+:[a-zA-Z0-9]+$"

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


def get_driver() -> Iterator[Driver]:
    global _driver_cache
    if _driver_cache is None:
        _driver_cache = create_driver()
    yield _driver_cache


def close_driver() -> None:
    global _driver_cache
    if _driver_cache is not None:
        _driver_cache.close()
        _driver_cache = None


@router.get("/health", response_model=schemas.GraphHealth)
def graph_health(driver: Driver = Depends(get_driver)):
    return schemas.GraphHealth(**service.graph_health(driver))


@router.get("/summary", response_model=schemas.GraphSummary)
def graph_summary(driver: Driver = Depends(get_driver)):
    return schemas.GraphSummary(**service.build_graph(driver))


@router.post("/sync", response_model=schemas.SyncResponse)
def sync_graph(driver: Driver = Depends(get_driver)):
    return schemas.SyncResponse(**service.sync_from_postgres(driver))


@router.get("/wallets/{wallet_id}/neighbors", response_model=schemas.BFSResponse)
def wallet_neighbors(
    wallet_id: str = Path(..., pattern=_WALLET_PATTERN),
    depth: int = Query(1, ge=1, le=6),
    max_nodes: int = Query(100, ge=1, le=1000),
    driver: Driver = Depends(get_driver),
):
    nodes = service.neighbors(driver, wallet_id, depth=depth, max_nodes=max_nodes)
    return schemas.BFSResponse(
        wallet_id=wallet_id,
        max_depth=depth,
        nodes=[schemas.Neighbor(**node) for node in nodes],
    )


@router.get("/wallets/{wallet_id}/bfs", response_model=schemas.BFSResponse)
def wallet_bfs(
    wallet_id: str = Path(..., pattern=_WALLET_PATTERN),
    depth: int = Query(3, ge=1, le=6),
    max_nodes: int = Query(100, ge=1, le=1000),
    driver: Driver = Depends(get_driver),
):
    nodes = service.bfs(driver, wallet_id, max_depth=depth, max_nodes=max_nodes)
    return schemas.BFSResponse(
        wallet_id=wallet_id,
        max_depth=depth,
        nodes=[schemas.Neighbor(**node) for node in nodes],
    )


@router.get("/wallets/{wallet_id}/dfs", response_model=schemas.DFSResponse)
def wallet_dfs(
    wallet_id: str = Path(..., pattern=_WALLET_PATTERN),
    depth: int = Query(6, ge=1, le=12),
    max_nodes: int = Query(100, ge=1, le=1000),
    driver: Driver = Depends(get_driver),
):
    nodes = service.dfs(driver, wallet_id, max_depth=depth, max_nodes=max_nodes)
    return schemas.DFSResponse(
        wallet_id=wallet_id,
        max_depth=depth,
        nodes=[schemas.WalletSummary(**node) for node in nodes],
    )


@router.get("/shortest-path", response_model=schemas.ShortestPathResponse)
def shortest_path(
    source: str = Query(..., pattern=_WALLET_PATTERN),
    target: str = Query(..., pattern=_WALLET_PATTERN),
    weight: str = Query("hops", pattern="^(hops|amount)$"),
    driver: Driver = Depends(get_driver),
):
    result = service.shortest_path(driver, source, target, weight=weight)
    return schemas.ShortestPathResponse(**result)


@router.get("/bfs-path", response_model=schemas.BFSPathResponse)
def bfs_path(
    source: str = Query(..., pattern=_WALLET_PATTERN),
    target: str = Query(..., pattern=_WALLET_PATTERN),
    driver: Driver = Depends(get_driver),
):
    result = service.bfs_shortest_path(driver, source, target)
    return schemas.BFSPathResponse(**result)


@router.get("/dfs-path", response_model=schemas.DFSPathResponse)
def dfs_path(
    source: str = Query(..., pattern=_WALLET_PATTERN),
    target: str = Query(..., pattern=_WALLET_PATTERN),
    driver: Driver = Depends(get_driver),
):
    result = service.dfs_path(driver, source, target)
    return schemas.DFSPathResponse(**result)


@router.get("/shortest-path-hops", response_model=schemas.HopsShortestPathResponse)
def shortest_path_hops(
    source: str = Query(..., pattern=_WALLET_PATTERN),
    target: str = Query(..., pattern=_WALLET_PATTERN),
    driver: Driver = Depends(get_driver),
):
    result = service.shortest_path_by_hops(driver, source, target)
    return schemas.HopsShortestPathResponse(**result)


@router.get("/weighted-path", response_model=schemas.WeightedPathResponse)
def weighted_path(
    source: str = Query(..., pattern=_WALLET_PATTERN),
    target: str = Query(..., pattern=_WALLET_PATTERN),
    weight: str = Query("hops", pattern="^(hops|amount)$"),
    driver: Driver = Depends(get_driver),
):
    try:
        result = service.weighted_path(driver, source, target, weight=weight)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return schemas.WeightedPathResponse(**result)


@router.get("/temporal-path", response_model=schemas.TemporalPathResponse)
def temporal_path(
    source: str = Query(..., pattern=_WALLET_PATTERN),
    target: str = Query(..., pattern=_WALLET_PATTERN),
    driver: Driver = Depends(get_driver),
):
    result = service.temporal_path_analysis(driver, source, target)
    return schemas.TemporalPathResponse(**result)


@router.get("/fund-flow", response_model=schemas.FundFlowResponse)
def fund_flow(
    source: str = Query(..., pattern=_WALLET_PATTERN),
    target: str = Query(..., pattern=_WALLET_PATTERN),
    driver: Driver = Depends(get_driver),
):
    result = service.fund_flow_analysis(driver, source, target)
    return schemas.FundFlowResponse(**result)


@router.get("/wallets/{wallet_id}/temporal-flow", response_model=schemas.TemporalFlowResponse)
def wallet_temporal_flow(
    wallet_id: str = Path(..., pattern=_WALLET_PATTERN),
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
    direction: str = Query("all", pattern="^(in|out|all)$"),
    max_results: int = Query(500, ge=1, le=5000),
    driver: Driver = Depends(get_driver),
):
    flows = service.temporal_flow(
        driver,
        wallet_id,
        from_ts=from_ts,
        to_ts=to_ts,
        direction=direction,
        max_results=max_results,
    )
    return schemas.TemporalFlowResponse(
        wallet_id=wallet_id,
        direction=direction,
        from_ts=from_ts,
        to_ts=to_ts,
        flows=[schemas.TemporalFlowRow(**flow) for flow in flows],
    )


@router.get("/clusters", response_model=schemas.ClustersResponse)
def wallet_clusters(
    algorithm: str = Query("louvain", pattern="^(wcc|louvain|leiden)$"),
    min_community_size: int = Query(2, ge=1, le=1000),
    driver: Driver = Depends(get_driver),
):
    try:
        communities = service.clusters(
            driver, algorithm=algorithm, min_community_size=min_community_size
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return schemas.ClustersResponse(
        algorithm=algorithm,
        communities=[schemas.Community(**item) for item in communities],
    )