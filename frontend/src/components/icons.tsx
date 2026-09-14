/**
 * Minimal inline icon set. All icons are stroke-based and inherit
 * `currentColor`, so they adapt to the surrounding text color.
 */

interface IconProps {
  size?: number;
}

function Svg({ size = 17, children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      width={size}
      height={size}
      aria-hidden
    >
      {children}
    </svg>
  );
}

export const DashboardIcon = () => (
  <Svg><rect x="3" y="3" width="7" height="9" rx="1" /><rect x="14" y="3" width="7" height="5" rx="1" /><rect x="14" y="12" width="7" height="9" rx="1" /><rect x="3" y="16" width="7" height="5" rx="1" /></Svg>
);

export const CasesIcon = () => (
  <Svg><path d="M4 6h16" /><path d="M4 12h16" /><path d="M4 18h16" /><circle cx="8" cy="6" r="1" fill="currentColor" /><circle cx="12" cy="12" r="1" fill="currentColor" /><circle cx="8" cy="18" r="1" fill="currentColor" /></Svg>
);

export const WalletIcon = () => (
  <Svg><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4" /><path d="M3 5v14a2 2 0 0 0 2 2h16v-5" /><path d="M18 12a2 2 0 0 0 0 4h4v-4Z" /></Svg>
);

export const TxIcon = () => (
  <Svg><path d="M13 2 3 14h7l-1 8 10-12h-7l1-8Z" /></Svg>
);

export const GraphIcon = () => (
  <Svg><circle cx="5" cy="12" r="2" /><circle cx="19" cy="5" r="2" /><circle cx="19" cy="19" r="2" /><path d="M7 11.5 17 6M7 12.5l9 5.5" /></Svg>
);

export const VaspIcon = () => (
  <Svg><path d="M12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26Z" /></Svg>
);

export const EvidenceIcon = () => (
  <Svg><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6" /><path d="m9 15 2 2 4-4" /></Svg>
);

export const RiskIcon = () => (
  <Svg><path d="M12 2 2 21h20Z" /><path d="M12 9v5" /><path d="M12 17.5v.01" /></Svg>
);

export const ReportIcon = () => (
  <Svg><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6" /><path d="M8 13h8M8 17h5" /></Svg>
);

export const AuditIcon = () => (
  <Svg><path d="M21 12a9 9 0 1 1-9-9c1.8 0 3.5.5 5 1.4L12 6" /><path d="M21 4v5h-5" /></Svg>
);

export const UsersIcon = () => (
  <Svg><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></Svg>
);

export const ShieldIcon = () => (
  <Svg><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" /></Svg>
);

export const SettingsIcon = () => (
  <Svg><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.01a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h.01a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.01a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" /></Svg>
);

export const SearchIcon = () => (
  <Svg><circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" /></Svg>
);

export const BellIcon = () => (
  <Svg><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" /></Svg>
);

export const ExplorerIcon = () => (
  <Svg><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><path d="M15 3h6v6" /><path d="M10 14 21 3" /></Svg>
);

export const TrashIcon = () => (
  <Svg><path d="M3 6h18" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><path d="M10 11v6M14 11v6" /></Svg>
);

export const ExportIcon = () => (
  <Svg><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="m7 10 5 5 5-5" /><path d="M12 15V3" /></Svg>
);

export const AddIcon = () => (
  <Svg><path d="M12 5v14M5 12h14" /></Svg>
);

export const TraceIcon = () => (
  <Svg><path d="M4 20 20 4" /><path d="m4 4 16 16" /><circle cx="4" cy="8" r="2" /><circle cx="8" cy="4" r="2" /><circle cx="20" cy="16" r="2" /><circle cx="16" cy="20" r="2" /></Svg>
);

export const LogoutIcon = () => (
  <Svg><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5" /><path d="M21 12H9" /></Svg>
);

export const MenuIcon = () => (
  <Svg><path d="M4 6h16M4 12h16M4 18h16" /></Svg>
);

export const ClockIcon = () => (
  <Svg><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></Svg>
);

export const CheckIcon = () => (
  <Svg><path d="m5 13 4 4L19 7" /></Svg>
);

export const SahyogIcon = () => (
  <Svg><rect x="2" y="3" width="20" height="18" rx="2" /><path d="M12 8v8" /><path d="M8 12l4 4 4-4" /></Svg>
);

export const SparkIcon = () => (
  <Svg><path d="M12 3v4M12 17v4M3 12h4M17 12h4" /><path d="M12 8a4 4 0 0 1 4 4 4 4 0 1 1-4-4Z" fill="currentColor" stroke="none" opacity="0.25" /><path d="m6 6 1.5 1.5M18 18l-1.5-1.5M18 6l-1.5 1.5M6 18l1.5-1.5" /></Svg>
);