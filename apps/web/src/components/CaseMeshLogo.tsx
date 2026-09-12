interface CaseMeshLogoProps {
  size?: number
}


function CaseMeshLogo({
  size = 44,
}: CaseMeshLogoProps) {
  return (
    <svg
      className="casemesh-logo"
      width={size}
      height={size}
      viewBox="0 0 48 48"
      role="img"
      aria-label="CaseMesh AI"
    >
      <defs>
        <linearGradient
          id="casemesh-logo-gradient"
          x1="8"
          y1="8"
          x2="40"
          y2="40"
          gradientUnits="userSpaceOnUse"
        >
          <stop
            offset="0"
            stopColor="#8aa2ff"
          />
          <stop
            offset="0.52"
            stopColor="#607cff"
          />
          <stop
            offset="1"
            stopColor="#52d6c7"
          />
        </linearGradient>
      </defs>

      <rect
        x="3"
        y="3"
        width="42"
        height="42"
        rx="13"
        fill="#0d1526"
        stroke="#273654"
      />

      <path
        d="M34.5 14.5C31.7 11.4 27.8 9.5 23.4 9.5C15.4 9.5 9 16 9 24C9 32 15.4 38.5 23.4 38.5C27.8 38.5 31.7 36.6 34.5 33.5"
        fill="none"
        stroke="url(#casemesh-logo-gradient)"
        strokeWidth="3.4"
        strokeLinecap="round"
      />

      <path
        d="M17 18L27 15L31 25L21 31L17 18Z"
        fill="none"
        stroke="#7f94d8"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      <path
        d="M17 18L31 25M27 15L21 31"
        fill="none"
        stroke="#455a8f"
        strokeWidth="1.2"
        strokeLinecap="round"
      />

      <circle
        cx="17"
        cy="18"
        r="2.5"
        fill="#8aa2ff"
      />

      <circle
        cx="27"
        cy="15"
        r="2.5"
        fill="#708aff"
      />

      <circle
        cx="31"
        cy="25"
        r="2.5"
        fill="#5fb8e8"
      />

      <circle
        cx="21"
        cy="31"
        r="2.5"
        fill="#52d6c7"
      />
    </svg>
  )
}


export default CaseMeshLogo