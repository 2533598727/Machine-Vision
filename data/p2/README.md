# P2 数据与标注说明

仓库中的 `manifest.json`、`images/` 和 `annotations/` 是一套程序生成的可重复性代理数据。它包含 10 组板书/试卷风格的参考图与受尺度、透视、光照、模糊和噪声影响的场景图，每组有 32 对控制点。控制点由生成器产生，`annotation_status` 明确标为 `generated_control_points_not_manual`，因此不能在课程提交中冒充“自采照片和手工标注”。

若需要满足作业中的真实数据条件，建议另建 `data/private/p2/`，保留当前代理数据及其结果以便核对。准备一张清晰、正视参考图与至少 10 张实际拍摄的场景图，场景应覆盖光照、远近尺度、失焦或运动模糊。涉及试卷姓名、学号时先脱敏，公开仓库前确认照片授权。`real-manifest.template.json` 给出 10 个采集条件的计划条目，不代表这些照片已采集；按实际条件修改后作为真实数据根目录的 `manifest.json`。

样本条目必须有 `source_type: "self_captured"`，并指定 `reference_image`、`scene_image`、`annotation` 相对路径。允许多个场景共用一张参考图。每个标注文件应包含至少 20 对同名点：

```json
{
  "image_id": "real_01",
  "annotation_status": "manual_verified",
  "reference_image": "images/real_01_reference.jpg",
  "scene_image": "images/real_01_scene.jpg",
  "points": [
    {"id": "p01", "label": "标题左上角", "reference": [120.0, 80.0], "scene": [132.5, 91.0]}
  ]
}
```

坐标使用图像左上角为原点，`x` 向右、`y` 向下，格式为 `[x, y]`。若不提供 `homography_scene_to_reference`，程序会由这些点估计场景到参考图的单应矩阵。标注应覆盖标题、文字行端点、框线角点、图形顶点和笔画交叉点等稳定位置，避免只集中在一个小区域。

`manual-annotation.template.json` 含 20 个空点对，`null` 坐标不能通过校验。用能显示像素坐标的图像查看器在两图中逐点点击记录；填写坐标、标签、标注者和复核者，检查点的语义一致性后再将状态改为 `manual_verified`，不可仅修改状态字符串来冒充人工标注。单应矩阵只适用于近似平面场景；本实现以全部控制点最小二乘拟合，输出重投影 RMSE，不剔除人工点。发现明显误标、畸变或纸面弯曲时，应修正数据或在报告中说明模型误差，不能把拟合误差视为独立测试精度。

在仓库根目录运行：

```powershell
python p2_multiscale_feature_matching.py --data-root data/private/p2 --require-manual --validate-only
python p2_multiscale_feature_matching.py --data-root data/private/p2 --require-manual --output-root output/p2-real --figure-root figures/p2-real
```

代理数据的复现实验命令是：

```powershell
python p2_multiscale_feature_matching.py --data-root data/p2
```

仅需重新生成代理数据时，使用 `--generate-synthetic --generate-only`，默认不覆盖已有文件。`--force` 仅用于明确希望覆盖代理数据的情形，不要对真实照片目录使用该命令。重新生成可能受字体版本影响，因此严格复现优先使用仓库内已有 PNG，并核对 `summary.json` 的输入哈希。

程序会在 `output/p2/` 写入逐图结果、消融结果、噪声/尺度结果和汇总 JSON，在 `figures/p2/` 写入 PDF/SVG 曲线、PNG 预览、消融图、数据缩略图和匹配示例。`--require-manual` 能检查字段、数量和坐标合法性，但不能鉴定照片或标注的真实来源；来源责任仍由提交者承担。
