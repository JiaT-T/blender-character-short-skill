# 示范视频来源与使用条件

此示范是非商业同人视频与 Blender 制作流程展示，不包含模型、贴图、工程或动作数据的分发。视频无音轨；画面不加入字幕或署名文字，完整借物信息在本页列明。

## 角色与模型

涅缇娅·亡歌／旖梦逝影。

模型制作：**战双帕弥什 / 1010浣**。角色及模型最终版权：**广州库洛科技有限公司**。

[原始配布页](https://www.aplaybox.com/details/model/huBrmYQe2u0m)。遵守原作者的非商业、视频用途及署名要求；模型无论修改与否均不得再分发，不得冒称为原创模型。公开的是渲染视频，原始及派生模型、纹理和 `.blend` 工程不在仓库中。

## 动作

使用 [Bandai Namco Research Motion Dataset 1](https://github.com/BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset) 中 `dataset-1_bye_happy_001` 与 `dataset-1_bow_normal_001`。

**2022 Bandai Namco Research Inc. All Rights Reserved.**

数据许可：[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)，[数据集原始 LICENSE](https://github.com/BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset/blob/master/dataset/Bandai-Namco-Research-Motiondataset-1/LICENSE)。此处为适配后的非商业视频，不分发 BVH 或派生动作文件。

修改包括：源朝向与脚部参考校准、目标比例拟合、现有 MMD/MMR 控制器绑定、动作衔接及停留、独立手指姿态和眨眼／微笑表情，以及分镜和剪辑。

## 渲染、场景与声音

在现有 MMD 骨架与用户已有 MMR 控制器上保留原有动作、表情、镜头和物理缓存，使用后续材质适配重渲染。角色外观参考 [华胥角色展示](https://huaxu.app/cn/wiki/constructs/wang-ge/model) 的保存源码及材质参数；相关材质实现、源纹理、环境图和后处理查找资源不随此视频发布。

刘海投影、眉眼透视和 Bloom 包含 Eevee 近似，不宣称与网页渲染逐像素一致。

简化剧场、灯光、镜头与剪辑为本示范制作内容；没有借用第三方场景或镜头动作。无音乐、配音或音效。

## 使用边界

本页不为角色、模型、动作或其他第三方资源授予统一许可证。CC BY-NC 4.0 对动作数据的授权不替代角色模型的独立条款；不得从示范视频的公开展示推断原始模型或工程可再分发。

示范反映本地后续制作结果，包含尚未作为通用代码发布的材质与渲染适配；它不表示只克隆当前仓库即可在没有外部资产和配置的情况下重建此片。解码通过、抽帧检查和用户对先前版本的认可均不等于这条新片已获正常速度整段视觉验收。
