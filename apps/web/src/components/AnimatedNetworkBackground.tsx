function AnimatedNetworkBackground() {
  return (
    <div
      className="animated-network-background"
      aria-hidden="true"
    >
      <div className="network-orb network-orb-a" />
      <div className="network-orb network-orb-b" />
      <div className="network-orb network-orb-c" />

      <svg
        className="network-mesh"
        viewBox="0 0 1600 1000"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <linearGradient
            id="network-blue"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="100%"
          >
            <stop
              offset="0%"
              stopColor="#5b78ff"
              stopOpacity="0"
            />
            <stop
              offset="42%"
              stopColor="#6d8cff"
              stopOpacity="0.62"
            />
            <stop
              offset="100%"
              stopColor="#50c6e8"
              stopOpacity="0"
            />
          </linearGradient>

          <linearGradient
            id="network-cyan"
            x1="100%"
            y1="0%"
            x2="0%"
            y2="100%"
          >
            <stop
              offset="0%"
              stopColor="#50c6e8"
              stopOpacity="0"
            />
            <stop
              offset="48%"
              stopColor="#4fb6d4"
              stopOpacity="0.48"
            />
            <stop
              offset="100%"
              stopColor="#6d8cff"
              stopOpacity="0"
            />
          </linearGradient>

          <radialGradient id="network-node-glow">
            <stop
              offset="0%"
              stopColor="#9fb0ff"
              stopOpacity="0.92"
            />
            <stop
              offset="100%"
              stopColor="#6d8cff"
              stopOpacity="0"
            />
          </radialGradient>
        </defs>

        <path
          className="network-path network-path-a"
          d="M-80 210 C240 60 430 340 720 220 S1210 40 1680 260"
          stroke="url(#network-blue)"
        />

        <path
          className="network-path network-path-b"
          d="M-120 720 C220 510 500 860 820 650 S1240 500 1700 720"
          stroke="url(#network-cyan)"
        />

        <path
          className="network-path network-path-c"
          d="M240 -90 C410 210 250 430 510 610 S930 790 1180 1090"
          stroke="url(#network-blue)"
        />

        <path
          className="network-path network-path-d"
          d="M1080 -120 C910 170 1120 410 910 610 S630 820 540 1080"
          stroke="url(#network-cyan)"
        />

        <g className="network-node-cluster network-cluster-a">
          <circle
            className="network-node-halo"
            cx="390"
            cy="250"
            r="30"
            fill="url(#network-node-glow)"
          />
          <circle
            className="network-node"
            cx="390"
            cy="250"
            r="3.5"
          />
          <circle
            className="network-node-small"
            cx="470"
            cy="325"
            r="2.2"
          />
          <line
            className="network-link"
            x1="390"
            y1="250"
            x2="470"
            y2="325"
          />
        </g>

        <g className="network-node-cluster network-cluster-b">
          <circle
            className="network-node-halo"
            cx="1125"
            cy="360"
            r="34"
            fill="url(#network-node-glow)"
          />
          <circle
            className="network-node"
            cx="1125"
            cy="360"
            r="3.5"
          />
          <circle
            className="network-node-small"
            cx="1215"
            cy="430"
            r="2.2"
          />
          <circle
            className="network-node-small"
            cx="1035"
            cy="455"
            r="2.2"
          />
          <line
            className="network-link"
            x1="1125"
            y1="360"
            x2="1215"
            y2="430"
          />
          <line
            className="network-link"
            x1="1125"
            y1="360"
            x2="1035"
            y2="455"
          />
        </g>

        <g className="network-node-cluster network-cluster-c">
          <circle
            className="network-node-halo"
            cx="770"
            cy="735"
            r="28"
            fill="url(#network-node-glow)"
          />
          <circle
            className="network-node"
            cx="770"
            cy="735"
            r="3.5"
          />
          <circle
            className="network-node-small"
            cx="690"
            cy="665"
            r="2.2"
          />
          <line
            className="network-link"
            x1="770"
            y1="735"
            x2="690"
            y2="665"
          />
        </g>
      </svg>

      <div className="network-signal network-signal-a" />
      <div className="network-signal network-signal-b" />
      <div className="network-signal network-signal-c" />
    </div>
  )
}


export default AnimatedNetworkBackground
