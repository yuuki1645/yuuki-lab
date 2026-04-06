export type LegId = "L" | "R";

export interface LegPose {
  hip1: number;
  hip2: number;
  knee: number;
  heel: number;
  heelRoll: number;
}

export type JointKey = keyof LegPose;

export type ActiveDrag = {
  leg: LegId;
  key: JointKey;
  axis: "x" | "y";
  // sign: 1 | -1;
  startClient: number;
  startAngle: number;
};
