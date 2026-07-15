import type { RoomAssetSummary } from "./App";

interface AssetLibraryPanelProps {
  assets: RoomAssetSummary[];
  onUseSceneBackground: (url: string) => void;
  onUseLayerImage: (url: string) => void;
  onUseAudio: (url: string) => void;
}

export function AssetLibraryPanel({ assets, onUseSceneBackground, onUseLayerImage, onUseAudio }: AssetLibraryPanelProps) {
  const images = assets.filter((asset) => asset.kind === "image");
  const audios = assets.filter((asset) => asset.kind === "audio");
  const categoryLabels: Record<RoomAssetSummary["category"], string> = { general: "其它", scene: "场景", character: "角色", audio: "音乐", effect: "音效" };
  return <section className="asset-library-panel">
    <div className="drawer-section-heading"><span>图片素材</span><small>{images.length} 项</small></div>
    <div className="asset-library-list">{images.map((asset) => <article className="asset-library-item" key={asset.asset_id}>
      <img src={asset.url} alt={asset.name} />
      <div><strong>{asset.name}</strong><small>{categoryLabels[asset.category]} · {asset.content_type}</small></div>
      <button type="button" onClick={() => onUseSceneBackground(asset.url)}>场景背景</button>
      <button type="button" onClick={() => onUseLayerImage(asset.url)}>图层</button>
    </article>)}{images.length === 0 && <p className="drawer-hint">上传场景背景或图层后，素材会出现在这里。</p>}</div>
    <div className="drawer-section-heading"><span>声音素材</span><small>{audios.length} 项</small></div>
    <div className="asset-library-list">{audios.map((asset) => <article className="asset-library-item asset-library-audio" key={asset.asset_id}>
      <audio controls preload="metadata" src={asset.url} />
      <div><strong>{asset.name}</strong><small>{categoryLabels[asset.category]} · {asset.content_type}</small></div>
      <button type="button" onClick={() => onUseAudio(asset.url)}>放入 BGM</button>
    </article>)}{audios.length === 0 && <p className="drawer-hint">上传 WAV、MP3 等音频后，素材会出现在这里。</p>}</div>
  </section>;
}
