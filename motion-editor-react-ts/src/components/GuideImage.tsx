import { GUIDE_MAP } from "../constants";
import { partKeyFromServoName } from "../utils";
import "./GuideImage.css";

interface GuideImageProps {
  servoName: string;
}

export default function GuideImage({ servoName }: GuideImageProps) {
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
    <div className="guide">
      <div className="guide-title">{getGuideTitle()}</div>
      <img
        className="guide-img"
        src={getGuideImage()}
        alt="guide"
        onError={(e) => {
          (e.target as HTMLImageElement).style.display = "none";
        }}
      />
    </div>
  );
}
