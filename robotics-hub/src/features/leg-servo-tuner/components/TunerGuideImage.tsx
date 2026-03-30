import { GUIDE_MAP } from "@/shared/constants";
import { partKeyFromServoName } from "@/shared/utils";

interface TunerGuideImageProps {
  servoName: string;
}

export default function TunerGuideImage({ servoName }: TunerGuideImageProps) {
  const getGuideImage = () => {
    if (!servoName) return GUIDE_MAP["KNEE"] ?? "/guides/knee.JPG";
    const key = partKeyFromServoName(servoName);
    return GUIDE_MAP[key] ?? GUIDE_MAP["KNEE"] ?? "/guides/knee.JPG";
  };

  const getGuideTitle = () => {
    if (!servoName) return "ガイド";
    const key = partKeyFromServoName(servoName);
    return `ガイド: ${key}`;
  };

  return (
    <div className="leg-tuner-guide">
      <div className="leg-tuner-guide-title">{getGuideTitle()}</div>
      <img
        className="leg-tuner-guide-img"
        src={getGuideImage()}
        alt="servo guide"
        onError={(e) => {
          (e.target as HTMLImageElement).style.display = "none";
        }}
      />
    </div>
  );
}
