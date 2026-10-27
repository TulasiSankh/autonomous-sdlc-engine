import React from 'react';

interface RobotAvatarProps {
  size?: number;
  className?: string;
}

export const RobotAvatar: React.FC<RobotAvatarProps> = ({ size = 36, className = '' }) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="robotAvatarHead" x1="8" y1="12" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop stopColor="#6366F1" />
          <stop offset="0.5" stopColor="#8B5CF6" />
          <stop offset="1" stopColor="#A855F7" />
        </linearGradient>
        <linearGradient id="robotAvatarVisor" x1="12" y1="18" x2="36" y2="30" gradientUnits="userSpaceOnUse">
          <stop stopColor="#0F172A" />
          <stop offset="1" stopColor="#1E293B" />
        </linearGradient>
        <linearGradient id="robotAvatarEye" x1="15" y1="21" x2="21" y2="25" gradientUnits="userSpaceOnUse">
          <stop stopColor="#38BDF8" />
          <stop offset="1" stopColor="#34D399" />
        </linearGradient>
        <linearGradient id="robotAvatarEyeRight" x1="27" y1="21" x2="33" y2="25" gradientUnits="userSpaceOnUse">
          <stop stopColor="#38BDF8" />
          <stop offset="1" stopColor="#34D399" />
        </linearGradient>
        <filter id="robotAvatarGlow" x="0" y="0" width="48" height="48" filterUnits="userSpaceOnUse">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>

      {/* Head Backing & Glow */}
      <rect x="6" y="10" width="36" height="30" rx="12" fill="url(#robotAvatarHead)" />

      {/* Antenna */}
      <path d="M24 10V4" stroke="#8B5CF6" strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="24" cy="4" r="3" fill="#34D399" filter="url(#robotAvatarGlow)" />

      {/* Ears */}
      <rect x="3" y="19" width="3" height="12" rx="1.5" fill="#A855F7" />
      <rect x="42" y="19" width="3" height="12" rx="1.5" fill="#A855F7" />

      {/* Visor Screen */}
      <rect x="11" y="15" width="26" height="18" rx="8" fill="url(#robotAvatarVisor)" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />

      {/* Eyes */}
      <rect x="16" y="20" width="5" height="6" rx="2.5" fill="url(#robotAvatarEye)" />
      <rect x="27" y="20" width="5" height="6" rx="2.5" fill="url(#robotAvatarEyeRight)" />

      {/* Smile / Visor Accent */}
      <path d="M21 28C22.2 29.2 25.8 29.2 27 28" stroke="#38BDF8" strokeWidth="1.5" strokeLinecap="round" />

      {/* Cheek glow accents */}
      <circle cx="14" cy="27" r="1" fill="#F472B6" opacity="0.6" />
      <circle cx="34" cy="27" r="1" fill="#F472B6" opacity="0.6" />
    </svg>
  );
};
