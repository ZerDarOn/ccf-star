import type { RoomAssetSummary } from "./App";
import type { RoomScene } from "./roomStore";

interface SceneBackgroundPanelProps {
  scene: RoomScene | null;
  assets: RoomAssetSummary[];
  backgroundUrl: string;
  blur: string;
  onBlurChange: (value: string) => void;
  onBackgroundChange: (url: string) => void;
  onSave: () => void;
}

export function SceneBackgroundPanel({ scene, assets, backgroundUrl, blur, onBlurChange, onBackgroundChange, onSave }: SceneBackgroundPanelProps) {
  const images = assets.filter((asset) => asset.kind === "image");
  return <section className="scene-background-panel">
    <div className="drawer-section-heading"><span>当前场景背景</span><small>{scene?.name ?? "未选择场景"}</small></div>
    <div className="scene-background-preview" style={backgroundUrl ? { backgroundImage: `url(${backgroundUrl})`, filter: `blur(${Math.min(Number(blur) || 0, 24) / 3}px)` } : undefined}>
      {!backgroundUrl && <span>尚未设置背景</span>}
    </div>
    <label>背景图片 URL<input value={backgroundUrl} onChange={(event) => onBackgroundChange(event.target.value)} placeholder="可粘贴图片地址，或从素材库选择" /></label>
    <label>背景虚化：{blur}px<input type="range" min="0" max="24" step="1" value={blur} onChange={(event) => onBlurChange(event.target.value)} /><small>只模糊背景层，不影响图层、Token、立绘和对话框。</small></label>
    <div className="drawer-section-heading"><span>场景图片素材</span><small>{images.length} 项</small></div>
    <div className="scene-background-assets">{images.map((asset) => <button type="button" key={asset.asset_id} onClick={() => onBackgroundChange(asset.url)}><img src={asset.url} alt={asset.name} /><span>{asset.name}</span></button>)}{images.length === 0 && <p className="drawer-hint">请先在素材库上传图片。</p>}</div>
    <button type="button" className="primary-action" disabled={!scene} onClick={onSave}>保存场景背景</button>
  </section>;
}
