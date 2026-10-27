import React from 'react';

export const RobotIllustration: React.FC = () => {
  return (
    <div className="hero-robot-container" aria-label="Orbit AI Robot Assistant">
      <svg
        viewBox="0 0 460 420"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="hero-robot-svg"
      >
        <defs>
          {/* Ambient Glow & Shadow Filters */}
          <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="16" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>

          <filter id="subtleShadow" x="-10%" y="-10%" width="120%" height="130%">
            <feDropShadow dx="0" dy="12" stdDeviation="16" floodColor="#6366F1" floodOpacity="0.16" />
          </filter>

          {/* Background Ambient Gradients */}
          <radialGradient id="bgOrb1" cx="50%" cy="50%" r="50%">
            <stop stopColor="#C4B5FD" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#EDE9FE" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="bgOrb2" cx="50%" cy="50%" r="50%">
            <stop stopColor="#93C5FD" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#E0F2FE" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="bgOrb3" cx="50%" cy="50%" r="50%">
            <stop stopColor="#6EE7B7" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#ECFDF5" stopOpacity="0" />
          </radialGradient>

          {/* Robot Body Material 3D Gradients */}
          <linearGradient id="robotHeadGrad" x1="150" y1="90" x2="310" y2="250" gradientUnits="userSpaceOnUse">
            <stop stopColor="#FFFFFF" />
            <stop offset="0.6" stopColor="#F1F5F9" />
            <stop offset="1" stopColor="#E2E8F0" />
          </linearGradient>

          <linearGradient id="robotVisorGrad" x1="165" y1="130" x2="295" y2="215" gradientUnits="userSpaceOnUse">
            <stop stopColor="#0B132B" />
            <stop offset="0.7" stopColor="#1C2541" />
            <stop offset="1" stopColor="#3A506B" />
          </linearGradient>

          <linearGradient id="eyeGlowGrad" x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#38BDF8" />
            <stop offset="1" stopColor="#34D399" />
          </linearGradient>

          <linearGradient id="earRingGrad" x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#818CF8" />
            <stop offset="1" stopColor="#C084FC" />
          </linearGradient>

          <linearGradient id="torsoGrad" x1="160" y1="240" x2="300" y2="350" gradientUnits="userSpaceOnUse">
            <stop stopColor="#FFFFFF" />
            <stop offset="0.5" stopColor="#F8FAFC" />
            <stop offset="1" stopColor="#E2E8F0" />
          </linearGradient>

          <linearGradient id="coreReactorGrad" x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#38BDF8" />
            <stop offset="0.5" stopColor="#818CF8" />
            <stop offset="1" stopColor="#34D399" />
          </linearGradient>

          <linearGradient id="orbitRingGrad" x1="60" y1="140" x2="400" y2="280" gradientUnits="userSpaceOnUse">
            <stop stopColor="#818CF8" stopOpacity="0.8" />
            <stop offset="0.5" stopColor="#C084FC" stopOpacity="0.4" />
            <stop offset="1" stopColor="#38BDF8" stopOpacity="0.7" />
          </linearGradient>
        </defs>

        {/* Ambient Floating Backdrop Shapes */}
        <ellipse cx="230" cy="220" rx="180" ry="150" fill="url(#bgOrb1)" />
        <circle cx="120" cy="140" r="110" fill="url(#bgOrb2)" />
        <circle cx="340" cy="270" r="100" fill="url(#bgOrb3)" />

        {/* Background Decorative Orbit Ellipse */}
        <ellipse
          cx="230"
          cy="225"
          rx="170"
          ry="65"
          stroke="url(#orbitRingGrad)"
          strokeWidth="2.5"
          strokeDasharray="6 8"
          transform="rotate(-15 230 225)"
          opacity="0.75"
        />

        {/* Floating Mini Tech Nodes / Spheres */}
        <g className="floating-node-1">
          <circle cx="85" cy="180" r="14" fill="#FFFFFF" filter="url(#subtleShadow)" />
          <circle cx="85" cy="180" r="8" fill="#818CF8" />
          <path d="M85 174L87 180H83L85 174Z" fill="#FFFFFF" />
        </g>

        <g className="floating-node-2">
          <circle cx="375" cy="160" r="16" fill="#FFFFFF" filter="url(#subtleShadow)" />
          <circle cx="375" cy="160" r="10" fill="#34D399" />
          <circle cx="375" cy="160" r="4" fill="#FFFFFF" />
        </g>

        <g className="floating-node-3">
          <rect x="335" y="275" width="28" height="28" rx="8" fill="#FFFFFF" filter="url(#subtleShadow)" />
          <circle cx="349" cy="289" r="6" fill="#38BDF8" />
        </g>

        {/* Floating Code Capsule Badge */}
        <g transform="translate(65, 255)" filter="url(#subtleShadow)">
          <rect width="112" height="34" rx="17" fill="#FFFFFF" stroke="rgba(99,102,241,0.15)" strokeWidth="1" />
          <circle cx="18" cy="17" r="6" fill="#10B981" />
          <text x="32" y="21" fontFamily="var(--font-sans)" fontSize="11" fontWeight="600" fill="#334155">
            Agent Active
          </text>
        </g>

        {/* Floating Verification Shield Badge */}
        <g transform="translate(295, 75)" filter="url(#subtleShadow)">
          <rect width="108" height="34" rx="17" fill="#FFFFFF" stroke="rgba(56,189,248,0.2)" strokeWidth="1" />
          <circle cx="18" cy="17" r="7" fill="#8B5CF6" />
          <text x="32" y="21" fontFamily="var(--font-sans)" fontSize="11" fontWeight="600" fill="#334155">
            100% Verified
          </text>
        </g>

        {/* ROBOT CHARACTER MAIN GROUP */}
        <g id="robotCharacter" filter="url(#subtleShadow)">
          {/* Cute Floating Magnetic Hands */}
          {/* Left Hand */}
          <g className="robot-hand-left">
            <ellipse cx="120" cy="270" rx="16" ry="13" fill="url(#torsoGrad)" stroke="#E2E8F0" strokeWidth="1.5" />
            <circle cx="120" cy="270" r="5" fill="#C084FC" />
          </g>

          {/* Right Hand */}
          <g className="robot-hand-right">
            <ellipse cx="340" cy="270" rx="16" ry="13" fill="url(#torsoGrad)" stroke="#E2E8F0" strokeWidth="1.5" />
            <circle cx="340" cy="270" r="5" fill="#38BDF8" />
          </g>

          {/* Torso */}
          <path
            d="M175 240C175 235 180 230 186 230H274C280 230 285 235 285 240L295 330C295 342 284 350 272 350H188C176 350 165 342 165 330L175 240Z"
            fill="url(#torsoGrad)"
            stroke="#CBD5E1"
            strokeWidth="1.5"
          />

          {/* Arc Reactor / Orbit Core */}
          <circle cx="230" cy="285" r="22" fill="#FFFFFF" stroke="#E2E8F0" strokeWidth="2" />
          <circle cx="230" cy="285" r="16" fill="url(#coreReactorGrad)" />
          <circle cx="230" cy="285" r="8" fill="#FFFFFF" opacity="0.9" />

          {/* Torso Detail Seams */}
          <path d="M190 252H270" stroke="#CBD5E1" strokeWidth="1" strokeLinecap="round" />
          <path d="M198 322H262" stroke="#CBD5E1" strokeWidth="1" strokeLinecap="round" />

          {/* Neck Joint */}
          <rect x="215" y="218" width="30" height="15" rx="5" fill="#94A3B8" />

          {/* Ears / Headset Pods */}
          {/* Left Ear */}
          <g>
            <rect x="135" y="142" width="16" height="42" rx="8" fill="url(#earRingGrad)" />
            <circle cx="143" cy="163" r="5" fill="#FFFFFF" opacity="0.8" />
          </g>

          {/* Right Ear */}
          <g>
            <rect x="309" y="142" width="16" height="42" rx="8" fill="url(#earRingGrad)" />
            <circle cx="317" cy="163" r="5" fill="#FFFFFF" opacity="0.8" />
          </g>

          {/* Head Shell */}
          <rect
            x="147"
            y="98"
            width="166"
            height="126"
            rx="46"
            fill="url(#robotHeadGrad)"
            stroke="#CBD5E1"
            strokeWidth="2"
          />

          {/* Antenna */}
          <path d="M230 98V62" stroke="#94A3B8" strokeWidth="4" strokeLinecap="round" />
          <circle cx="230" cy="58" r="10" fill="#34D399" filter="url(#softGlow)" />
          <circle cx="230" cy="58" r="5" fill="#FFFFFF" />

          {/* Dark Glass Visor Screen */}
          <rect
            x="167"
            y="120"
            width="126"
            height="82"
            rx="28"
            fill="url(#robotVisorGrad)"
            stroke="rgba(255,255,255,0.25)"
            strokeWidth="1.5"
          />

          {/* Visor Glare / Reflection */}
          <path
            d="M178 132C192 126 220 124 245 125C222 135 188 148 181 165C178 152 176 138 178 132Z"
            fill="#FFFFFF"
            opacity="0.12"
          />

          {/* Glowing Eyes */}
          {/* Left Eye */}
          <g>
            <rect x="187" y="144" width="22" height="26" rx="10" fill="url(#eyeGlowGrad)" />
            {/* Eye Pupil / Highlight */}
            <circle cx="194" cy="152" r="3.5" fill="#FFFFFF" />
          </g>

          {/* Right Eye */}
          <g>
            <rect x="251" y="144" width="22" height="26" rx="10" fill="url(#eyeGlowGrad)" />
            {/* Eye Pupil / Highlight */}
            <circle cx="258" cy="152" r="3.5" fill="#FFFFFF" />
          </g>

          {/* Friendly Smile Indicator */}
          <path
            d="M214 184C221 190 239 190 246 184"
            stroke="#38BDF8"
            strokeWidth="3"
            strokeLinecap="round"
          />

          {/* Cute Cheek Blush Highlights */}
          <ellipse cx="178" cy="176" rx="5" ry="3" fill="#F472B6" opacity="0.5" />
          <ellipse cx="282" cy="176" rx="5" ry="3" fill="#F472B6" opacity="0.5" />
        </g>
      </svg>
    </div>
  );
};
