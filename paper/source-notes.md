# 文献核验记录

核验日期：2026-09-07。本文是聚焦机制和方案的叙述性技术综述，不宣称覆盖全部研究，也没有执行性能实验。

现有14条文献，包括10篇英文论文与4篇中文论文，正文按首次出现顺序引用。书目标题、作者、年份、出版物和DOI通过Crossref元数据核验；方法与数据集的关键边界另参照下列来源。没有复制或发布第三方论文全文。

| 条目 | 原始来源及核验重点 |
| --- | --- |
| [1] | [Buchsbaum DOI](https://doi.org/10.1016/0016-0032(80)90058-7)：1980，310(1)，1-26。 |
| [2] | [Land与McCann DOI](https://doi.org/10.1364/JOSA.61.000001)：1971，61(1)，起页1。Crossref只列起页；终页1-11为通行书目记录，未将其描述为Crossref提供的完整页码。 |
| [3] | [Jobson等 DOI](https://doi.org/10.1109/83.597272)：1997，6(7)，965-976；多尺度Retinex。 |
| [4] | 王奎、黄福珍，[基于光照补偿的HSV空间多尺度Retinex图像增强](https://doi.org/10.3788/LOP202259.1010004)：《激光与光电子学进展》2022，59(10)，1010004；文中只引用其研究方向，不推断其文档OCR效果。 |
| [5] | 贾洪博、石蕴玉、刘翔、赵静文，[基于光照重映射的低照度图像增强算法](https://doi.org/10.3788/LOP202158.2210014)：《激光与光电子学进展》2021，58(22)，2210014；用于讨论低照度亮度调整与文档校色的差异。 |
| [6] | [Reinhard等 DOI](https://doi.org/10.1109/38.946629)：2001，21(4)，34-41；统计色彩迁移不是深度方法。Crossref将Ashikhmin误拼为Adhikhmin，采用作者正确拼写。 |
| [7] | [FC4，CVF原始页面](https://openaccess.thecvf.com/content_cvpr_2017/html/Hu_FC4_Fully_Convolutional_CVPR_2017_paper.html)：局部估计置信度加权后得到全局照明；采用CVF页码4085-4094，Crossref/IEEE页码为330-339。 |
| [8] | 杨泽鹏、解凯、李桐、杨梦瑶、杨斌，[多通道置信度加权颜色恒常性算法](https://doi.org/10.3788/AOS202141.1133002)：《光学学报》2021，41(11)，1133002；用于补充置信度加权研究，不将“多通道”误写为多光源文档校正。 |
| [9] | [Deep White-Balance Editing，CVF原始页面](https://openaccess.thecvf.com/content_CVPR_2020/html/Afifi_Deep_White-Balance_Editing_CVPR_2020_paper.html)：处理ISP渲染后的sRGB白平衡；采用CVF页码1397-1406，Crossref/IEEE页码为1394-1403。 |
| [10] | [DocTr作者仓库](https://github.com/fh2019ustc/DocTr)：GeoTr几何模块与IllTr光照模块，后者使用DocProj训练；不将几何模块成绩移用为本方案色彩校正收益。ACM DOI对应2021年273-281页。 |
| [11] | 李悦敏、徐海松、黄益铭、杨敏航、胡兵、张云涛，[应用环境光传感器的颜色恒常性算法](https://doi.org/10.3788/AOS230458)：《光学学报》2023，43(14)，1433001；中文摘要说明镜头旁环境光传感器、传感器置信度评估和低颜色复杂度场景。本文不假定常规手机具备论文中的标定条件。 |
| [12] | [SSIM DOI](https://doi.org/10.1109/TIP.2003.819861)：正式刊期为2004，13(4)，600-612；DOI中的2003不是本文引用年份。 |
| [13] | [Sharma作者资料页](https://www.ece.rochester.edu/~gsharma/ciede2000/)：作者明确给出2005年2月、30(1)、21-30，另提供标准测试对。Crossref的最早在线年份2004不替代正式刊期。 |
| [14] | [MIT-Adobe FiveK官网](https://data.csail.mit.edu/graphics/fivek/)：5000张RAW自然照片，每图五位修图者以悦目为目标调整；不是文档照明的物理真值。 |

中文文献核验范围：四条书目的中文题名、全体作者、年份、卷期及文章编号均与Crossref DOI记录核对，并通过OpenAlex再次确认标题。其中[11]的中文摘要通过[OpenAlex条目](https://api.openalex.org/works/https://doi.org/10.3788/aos230458)读取。部分出版平台页面触发访问验证，未读取这些论文全文；[4][5][8]只据可核验的题名与书目信息描述研究方向，不编造网络结构、实验数据或性能结论。四篇中文论文的七位数末尾字段为文章编号，不是起止页码。正文中的文档适配边界是本综述的分析，不冒充原论文的实验结论。

FiveK许可原文：[Adobe研究许可](https://data.csail.mit.edu/graphics/fivek/legal/LicenseAdobe.txt)、[Adobe与MIT研究许可](https://data.csail.mit.edu/graphics/fivek/legal/LicenseAdobeMIT.txt)。两者限定研究目的，要求保留版权和许可；“公开可下载”不等于无条件商用。本文未引入FiveK图像。

LoDoPaB-CT仅用于说明任务适配边界，并非本综述的校色实验数据来源。所有计划规模、时间与阈值均为本项目设计，不是引用论文报告的实验结果。
