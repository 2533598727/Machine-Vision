# Machine Vision

P1：文档图像偏色与光照不均的技术综述及视觉数据收集方案。

## 提交材料

- [综述 PDF（LaTeX排版）](output/pdf/p1-review.pdf)
- [采集方案示意图 PNG（2880×2280）](figures/collection-plan.png)
- [完整综述 Markdown](output/review.md)

正文 **2575字**：按汉字逐字计数、英文词与数字串各计1字，含摘要及采集方案；不含标题、章节名、关键词、行内与独立数学表达式、引文序号、图中文字及参考文献。正文包含2516个汉字、59个英文词与数字串，满足2500-3000字要求。不同软件的“字符数（含标点）”不是本口径。

综述包含10篇真实文献，正文采用顺序编码引用；PDF引文可跳转参考文献，DOI可点击。内容包括成像物理、Gray World、White Patch、Retinex、色彩迁移、FC4、深度白平衡、文档光照校正，以及PSNR、SSIM、ΔE00和任务级评价。

成像积分、PSNR、灰块亮度比及均匀性使用真正的LaTeX数学环境编译，包含标准分式、积分、上下标与3组自动公式编号，不是用普通文字或截图模拟公式。

## 数据状态

**这是数据收集方案，不是已采集数据集。** 没有虚构采集记录、样本图片或实验分数。

| 项目 | 计划数量 |
| --- | ---: |
| 独立原稿 | 24份，4类各6份 |
| 场景图像 | 24稿 × 2设备 × 5光照 = 240张 |
| 同机参考图像 | 24稿 × 2设备 = 48张 |
| 图像总量 | 288张，RAW副本、预试拍与校准伴拍不重复计数 |
| 训练/验证/测试 | 16/4/4稿，对应160/40/40张场景图 |

参考、设备变体和增强样本跟随原稿分组，避免内容泄漏。所有质量阈值是待预试校准的项目约定，不是通用行业标准。固定OCR和版面模型比较校正前后效果，不预设收益。

![视觉数据收集方案](figures/collection-plan.png)

## 可编辑文件

- [正文源稿](paper/review.md)、[结构化文献](paper/references.json)、[BibTeX](paper/references.bib)
- [可直接编译的LaTeX源文件](paper/p1-review.tex)、[LaTeX样式配置](paper/latex-preamble.tex)
- [文献核验与书目差异说明](paper/source-notes.md)
- [采集操作规范](data/collection-protocol.md)、[机器可读计划](data/collection-plan.json)
- [空白标注模板](data/annotation-template.json)：`null`表示待填，默认不允许公开。
- [示意图 HTML](figures/collection-plan.html)、[矢量 SVG](figures/collection-plan.svg)

示意图以HTML为源、内联SVG为图形，按流程图区分质检分支与返工路径。当前中文渲染使用系统字体（Microsoft YaHei/SimSun后备）；SVG在其他系统可能替换字体，PNG保持一致。无需开发服务器，HTML可直接打开。

## 复现

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

生成文件位于 `output/` 与 `figures/`。[构建审计](output/build-audit.json)和[验证结果](output/verification.json)记录字数、引用、数量一致性、PDF字体嵌入及图像非空检查；最终PDF也已逐页目视检查。验证脚本不能替代真实数据和下游实验。

## 版权与隐私

本仓库只包含原创综述、方案、示意图、空白模板和构建代码，没有学生原图、教材扫描、第三方论文全文或FiveK照片。正式采集需取得适用授权，公开副本脱敏并移除定位信息；签名与身份映射不进入Git历史。第三方资源遵循各自许可，公开仓库不改变其版权。

仓库名称采用 `Machine-Vision`，因为GitHub仓库名不支持空格；项目标题保留“Machine Vision”。
