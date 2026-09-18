# Machine Vision

《机器视觉算法与应用》课程作业仓库，收录 P1 文档成像综述与数据采集方案，以及 P2 多尺度特征匹配质量评测实验。

## 作业导航

| 作业 | 主题与状态 | 主要材料 |
| --- | --- | --- |
| P1 | 文档图像偏色与光照不均；已完成综述与采集方案，采集数量为计划目标 | [报告 PDF](output/pdf/p1-review.pdf) · [正文 Markdown](output/review.md) · [采集规范](data/collection-protocol.md) |
| P2 | 多尺度特征匹配质量评测；已完成实拍教材页标注、实验与报告，来源边界见下文 | [提交包 ZIP](output/p2-real-submission.zip) · [报告 PDF](output/pdf/p2-report-real.pdf) · [单文件代码](p2_multiscale_feature_matching.py) · [详细说明](P2_REAL_README.md) |

## P2 多尺度特征匹配质量评测

Lab2 第 3 周周四：可重复性消融实验。当前提交版本使用 12 张实拍教材页照片，以 `IMG_0260.JPG` 为参考形成 11 组图像对；共保留 250 对同名点，每组 20-24 对，输出 3,245 行逐图评测。

### 实验内容

- 空域特征：Sobel、LoG、Harris、Shi-Tomasi、SIFT。
- 频域预处理：FFT 理想/高斯低通、高通，以及不滤波对照。
- 多尺度：1 层对照与 2-3 层图像金字塔，另测数字缩放和附加噪声下的重复率。
- 指标：特征重复率、匹配正确率、定位误差、运行时间，并保留接受/正确匹配数量及有效图对数。
- 消融：分别关闭外部金字塔、频域滤波、共同非极大值抑制（NMS）。

所有 P2 功能均在一个 `.py` 文件中实现，关键步骤附注释。报告包含指标公式、曲线、实验分析及计算摄影链路讨论；当前材料已通过 10 项自检、结果一致性核对和提交包解压测试。

### 提交与结果

- [完整实拍提交包](output/p2-real-submission.zip)：含唯一 P2 `.py`、12 张工作照片、11 份最终标注、报告、曲线、CSV 和复现说明。
- [实拍报告 PDF](output/pdf/p2-report-real.pdf)与[成果说明文字](output/p2-real/submission-text.txt)。
- [单一 Python 实现](p2_multiscale_feature_matching.py)与[固定版本依赖](requirements-p2.txt)。
- [逐图结果与汇总](output/p2-real/)、[结果一致性记录](output/p2-real/verification.json)、[提交包核验记录](output/p2-real-package-check.json)。
- [曲线与标注预览](figures/p2-real/)、[几何质量记录](figures/p2-real/annotation-quality.json)、[初选点记录](data/p2-real-landmarks.json)、[助手复核记录](data/p2-annotation-review.json)。
- [报告 LaTeX 源](paper/p2-report-real.tex)、[数值与分析源](paper/p2-real-results.tex)、[详细数据及复现说明](P2_REAL_README.md)。

### 数据来源与版本

照片为同一份教材的书页，而非题目指定的板书或试卷。点对由助手视觉选点、局部灰度配准辅助及逐点放大核对完成，不冒充学生亲手标注；状态为 `assistant_visual_verified`、`human_verified=false`，严格人工模式 `--require-manual` 会拒绝当前标注。这两项与作业字面要求的偏差已在报告中说明。

工作照片为去除 EXIF/GPS 的 960×1280 副本，原始照片未上传。`data/private/p2/` 受 Git 忽略，工作照片与最终标注由提交包分发；公开的 ZIP、报告和预览仍包含照片内容，Git 忽略不等于这些内容不公开。书页弯曲使单应几何参照带有近似误差，匹配比例应结合数量与几何残差解读。

[旧合成代理验证版](P2_README.md)保留在 `data/p2/`、`output/p2/`、`figures/p2/`，对应 `p2-report.pdf` 和 `p2-submission.zip`，仅作流程验证，不与当前实拍提交材料混用。

### P2 快速复现

建议 Python 3.12。从仓库根目录将实拍提交包解压到一个新目录，再进入该目录运行；照片和最终标注已包含在包内，不依赖原始 D 盘路径：

```powershell
Expand-Archive -LiteralPath output/p2-real-submission.zip -DestinationPath tmp/p2-real-reproduction
Set-Location tmp/p2-real-reproduction
python -m pip install -r requirements-p2.txt
python p2_multiscale_feature_matching.py --self-test
python p2_multiscale_feature_matching.py --data-root data/private/p2 --validate-only
python p2_multiscale_feature_matching.py --data-root data/private/p2 --output-root output/p2-real --figure-root figures/p2-real
```

P2 实验不需要浏览器、GUI 或 LaTeX；仅重新编译报告时需要 Tectonic 或 XeLaTeX。再次运行会覆盖解压目录内指定的实验结果与图表，不会自动修改 PDF 中的数字，运行时间也会随硬件负载变化。不要通过重新导入原图覆盖最终标注来代替复现，完整说明见 [P2_REAL_README.md](P2_REAL_README.md)。

## P1 文档成像综述与采集方案

主题：文档图像偏色与光照不均的技术综述及视觉数据收集方案。以下 288 张图像和数据划分均为 P1 的采集计划，不代表已完成采集，也不是 P2 的实拍数据统计。

### 提交材料

- [综述 PDF（LaTeX排版）](output/pdf/p1-review.pdf)
- [采集方案示意图 PNG（2880×2280）](figures/collection-plan.png)
- [完整综述 Markdown](output/review.md)

### 采集计划

| 项目 | 计划数量 |
| --- | ---: |
| 独立原稿 | 24份，4类各6份 |
| 场景图像 | 24稿 × 2设备 × 5光照 = 240张 |
| 同机参考图像 | 24稿 × 2设备 = 48张 |
| 图像总量 | 288张，RAW副本、预试拍与校准伴拍不重复计数 |
| 训练/验证/测试 | 16/4/4稿，对应160/40/40张场景图 |

参考、设备变体和增强样本跟随原稿分组，避免内容泄漏。所有质量阈值是待预试校准的项目约定，不是通用行业标准。固定OCR和版面模型比较校正前后效果，不预设收益。

![视觉数据收集方案](figures/collection-plan.png)

### 可编辑文件

- [正文源稿](paper/review.md)、[结构化文献](paper/references.json)、[BibTeX](paper/references.bib)
- [可直接编译的LaTeX源文件](paper/p1-review.tex)、[LaTeX样式配置](paper/latex-preamble.tex)
- [文献核验与书目差异说明](paper/source-notes.md)
- [采集操作规范](data/collection-protocol.md)、[机器可读计划](data/collection-plan.json)
- [空白标注模板](data/annotation-template.json)：`null`表示待填，默认不允许公开。
- [示意图 HTML](figures/collection-plan.html)、[矢量 SVG](figures/collection-plan.svg)

示意图以HTML为源、内联SVG为图形，按流程图区分质检分支与返工路径。当前中文渲染使用系统字体（Microsoft YaHei/SimSun后备）；SVG在其他系统可能替换字体，PNG保持一致。无需开发服务器，HTML可直接打开。

### P1 复现

需要Python 3.10+、XeLaTeX或Tectonic，以及可用的Chromium、Edge或Chrome。PDF使用`ctexart`和`amsmath`，由XeTeX引擎完成中文与数学排版；示意图由Playwright渲染。Windows字体取自系统，不在仓库分发字体文件。

```powershell
python -m pip install -r requirements.txt
python scripts/build_artifacts.py --browser-channel msedge
python scripts/verify_artifacts.py
```

LaTeX引擎会从PATH查找，也可通过 `--tex-engine` 或 `P1_TEX_ENGINE` 指定路径。本次采用官方Tectonic 0.17.0 Windows便携版，运行文件与下载缓存没有提交到仓库。初次运行Tectonic需要联网按需下载TeX宏包；传统XeLaTeX环境需要安装`ctex`及所用宏包。

若使用Playwright自带的浏览器，先运行 `python -m playwright install chromium`，再运行不带 `--browser-channel` 的构建命令。其他系统会优先使用Noto CJK，再后备到Fandol字体；可在样式配置中修改字体。

只编译现有LaTeX源文件，可在 `paper/` 目录运行：

```powershell
tectonic p1-review.tex --outdir ../output/pdf
```

也可使用XeLaTeX连续编译两次以解析引文和图号。`paper/p1-review.tex`是完整生成稿；再次运行构建脚本会依据Markdown和文献JSON覆盖它，长期修改应同步到这些源文件。

已生成PNG且只改正文时，可用 `python scripts/build_artifacts.py --skip-diagram`。该选项不会更新示意图，不应用于修改示意图后的完整构建。

可选视觉复核（需Poppler）：

```powershell
New-Item -ItemType Directory -Force tmp/pdfs
pdftoppm -scale-to 1400 -png output/pdf/p1-review.pdf tmp/pdfs/review
```

生成文件位于 `output/` 与 `figures/`。
