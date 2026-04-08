# 参考视频抽帧（可选）

参考素材：`public/reference/cockpit-ref.mp4`（与 `Downloads` 中同名文件一致）。

本地已安装 **ffmpeg** 时，可在仓库根目录执行：

```bash
mkdir -p aiagent/frontend/docs/cockpit-ref-frames
ffmpeg -y -i aiagent/frontend/public/reference/cockpit-ref.mp4 \
  -vf "select='not(mod(n\,45))',scale=1280:-1" -vsync vfr \
  aiagent/frontend/docs/cockpit-ref-frames/frame_%03d.png
```

或按时间截取单帧：

```bash
ffmpeg -ss 00:00:02 -i aiagent/frontend/public/reference/cockpit-ref.mp4 -vframes 1 aiagent/frontend/docs/cockpit-ref-frames/preview.png
```

用于对照调色与布局；**不必**提交到 Git（可将本目录加入 `.gitignore`）。
