/**
 * スケッチ風 SVG 用の共有フィルタ（feTurbulence + feDisplacementMap）
 */
export function PoseSketchFilters() {
  return (
    <defs>
      <filter id="pose-wobble" x="-5%" y="-5%" width="110%" height="110%">
        <feTurbulence
          type="fractalNoise"
          baseFrequency="0.04"
          numOctaves="2"
          result="noise"
        />
        <feDisplacementMap in="SourceGraphic" in2="noise" scale="1.2" />
      </filter>
    </defs>
  );
}
