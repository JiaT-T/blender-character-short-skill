# 来源与第三方权利

本仓库当前整理 `blender-character-short` v45a 通用 skill，冻结生产者标识为 v45a-local。v43a 与 v33 的清单保存在 release/history；当前源 ZIP 身份和分发差异见 release/distribution-manifest.json。Python 脚本保持本地冻结包原字节，本次仅调整公开入口说明与发布文档，没有更换或扩大原有许可。

部分材质、轮廓与后处理实现根据 Huaxu 模型查看器的源公式或运行观察整理，不应据此主张拥有其上游实现、数据或美术资产的权利。例如 `scripts/smaa_cpu.py` 自述为 Huaxu `C69G59uD2.js` 三段 SMAA 的 NumPy 翻译，并保留其 `SOURCE_SHA256`：

```text
172188ea0193106745299323b5b2e2ac9cc8b7d33535e6d538798b1685dd8d9e
```

原有来源说明、来源哈希与适用范围均予保留；本次整理未独立确认这些来源是否允许再许可。因此不添加 MIT、Apache 或其他覆盖全部代码的许可证，也不将来源公式或源派生代码重新宣称为原创。对外复用或再分发前，使用者须确认适用权利与条款。

Blender、mmd_tools、NumPy、Pillow、imageio-ffmpeg、FFmpeg 与各自的外部依赖拥有独立的权利和许可要求。本仓库不打包这些软件、wheels、可执行文件或依赖源码。

角色模型、PMX/GLB、纹理、LUT、SMAA Area/Search 图、音频、源网页资源和角色专用配置不随本仓库分发。使用者须自行取得授权，保存原作者归属，并遵守模型、角色和资源的使用条款。本仓库没有授予这些资源的任何许可。

## 外部动作与场景资源

`source_motion.py` / `source_motion_layer.py` 处理用户另行提供的许可动作与节点层级；配套验证脚本仅生成自有合成旋转数据。既有 Stand02 动作和节点层级的外部再分发权尚未核实，原数据和提取后的数据均未发布。

独立的本地走近后接物试作用过 Khronos glTF Sample Assets 中的 [CesiumMan](https://github.com/KhronosGroup/glTF-Sample-Assets/blob/main/Models/CesiumMan/README.md)。其作者标注为 © 2017 Cesium，模型关联文件列为 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)；[官方许可文件](https://github.com/KhronosGroup/glTF-Sample-Assets/blob/main/Models/CesiumMan/LICENSE.md)另列徽标和商标的权利边界。这不构成对本仓库代码的统一许可。

本次通用发布没有附带 CesiumMan 模型、徽标、原始或提取后的骨架/动画，也没有发布该试作的角色专用重定向及组合代码，因此没有将其派生动作数据放入通用配置。需要此资源时从官方模型目录单独获取，保存实际版本、作者、许可、修改记录和所需署名；对提取、重定向、时间裁切等修改明确说明，不把动作资源的许可扩大到目标角色模型。

静态场景导入只包含通用文件校验和导入逻辑。外部场景、纹理及授权文件不随包分发；自制临时测试几何也不作为资源包发布。

v26c 的 GLB 动作转换器只包含通用转换代码和自有合成验证脚本。转换输出及真实输入的权利记录均未打包。工具保留支持的来源、署名、许可、附加限制、修改说明和精确源/许可字节哈希，并拒绝未知或重复字段；这些机制保存声明，不能确认声明者拥有使用或再分发权。外观引用被移除也不解除原动作的许可限制。

v33 的配置式身体适配继续要求外部源动作、匹配层级、转换报告、原始 GLB 和权利记录，并核对其实际身份。仓库只发布通用代码；角色映射、私有编排、原始及派生动作、工程和影片不随代码公开。

历史v33本地交接核对的模型署名要求为 **模型：战双帕弥什/白泽**。PMX 注释另记 `From B.y.Zantine`，不推断两者身份关系。随附模型条款禁止模型及改模再分发；该模型、原始 Readme、纹理和派生工程均未收入公开仓库。此处保留署名记录不授予素材使用或再分发许可。

## v43a 补充

本次继续仅发布通用代码和文档，未扩大既有许可，也未打包MMD Tools、MikuMikuRig或Rigify。
本地动作试作另行使用Bandai Namco Research Motiondataset dataset1的许可片段；
该数据集注明2022 Bandai Namco Research Inc. All Rights Reserved，CC BY-NC4.0。
原始BVH、拟合后的目标、重定向和剪辑派生数据，以及使用它们的影片均不随仓库发布。
未来另行取得资产时仍须保留实际作者、许可、非商业限制、修改和署名记录。

现有用户控制器修复调用Blender原生骨骼/约束接口，并要求外部角色映射。
教程与已核查插件接口的引用见专门文档；自动生成失败、原物理崩溃和未完成验收均保留。
代码、素材和插件的权利彼此独立，不因本次通用工具发布而取得第三方资源再分发权。


## v45a 补充

新增控制器基线、工程身份、通用 packed look 迁移、保存工程渲染与测试代码使用 Blender/Python 的公开接口；本次不打包 MMD Tools、MikuMikuRig、Rigify 的实现或 h07 的角色工程、材质资产和纹理。直接生成控制器调用另行安装的 MMR，不重新声称拥有插件代码。模型级控制配置仍在仓库外。

Windows 硬件枚举使用 DXCore 公开接口标识与属性，不包含 Windows SDK 头文件。标识可核对 Microsoft [DirectX-Headers 的 dxcore_interface.h](https://github.com/microsoft/DirectX-Headers/blob/main/include/directx/dxcore_interface.h)；该上游项目声明 MIT，不能据此为本仓库其他来源代码授予统一许可。

既有 README 示范、封面和借物说明没有修改或重新发布素材；本轮新增的技术片和全部工程保持本地。通用迁移器的发布不授予其外部 look donor 或角色材质的使用/再分发权。
