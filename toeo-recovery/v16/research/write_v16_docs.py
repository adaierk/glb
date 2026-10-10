"""Write delivery notes only after the actual native milestone passes."""
import json
from pathlib import Path

def main():
 root=Path(__file__).resolve().parents[1]
 proof=json.loads((root/'new_evidence/native/v16_actual_bag_hud_milestone.json').read_text())
 assert proof['passed'] and proof['visual_reviewed']
 readme='''永恒传说 Online 本地恢复 v16：原 HP/TP 显示与背包顺序恢复
日期：2026-10-10

本版继续使用原 Windows 客户端、地图、界面和图像。已通过实际鼠标操作与重启验证：
进入拉修安河口、打开商店、买卖软糖、右键详情、自选目标后使用、背包位置交换、
原 HP/TP 栏绘制，以及物品顺序、金币、生命值、位置恢复。
截图来自原客户端，仅裁去桌面。完整游戏尚未完成。

启动方法（Windows）
1. 解压到独立目录，需要 Python 3；首次启动自动安装 frida 和 pillow。
2. 运行 Run_TOEO_Rashuan.cmd，选择已有完整且修正布局的原客户端目录。
   该目录需要 ToEO_CL.dat、data/map、data/resource、data/ui、data/help。
   只有旧完整 ZIP 或 client_pack.7z 时，先运行 Prepare_TOEO_Client.cmd；需要 7-Zip。
3. 按原界面开始、同意协议、选择区服。账号 archive001，密码 local123。
   选择角色后点击「ゲームスタート」；首次提示取消两项介绍后点击「確定」。
4. 左键选中码头商人，再点击一次，打开商店。
   「購入」页双击商品加入购物车，右侧箭头调数量，再点击「購入」。
   「売却」页双击持有物品，调整数量，再点击「売却」；× 关闭商店。
5. 左侧第二个图标打开原物品窗口。右键软糖显示详情，双击尝试使用。
   当前仅支持自己；若目标仍是商人，先关闭物品窗口，按 Enter 输入 /target，
   再按 Enter 选中自己，再打开物品窗口双击道具。命令不带参数。
6. 在背包物品格之间拖动，可交换两件物品的位置；拖到后方空位则移到列表末尾。
   原背包采用连续排列，使用完最后一件或售空后，后续物品会补位。
7. 关闭窗口后可在已开放码头行走。关闭游戏和服务后再启动，会恢复上述状态。
   控制台 Ctrl+C 停止服务；没有十分钟自动结束。

升级与原文件
关闭旧游戏和服务，把旧包的 local_world_userdata 复制到新版同名位置。
旧存档自动添加背包位置字段，保留金币、物品实例和生命值，不重复发金币。
新版自动建立独立的 toeo_runtime_cache_v16 运行目录；原客户端目录和 EXE 保留。
仅在运行目录把四张旧调色板纹理无损展开为 32 位，保留颜色、透明度和方向。
缓存不属于角色存档，后续升级可以重新生成。原完整资源继续使用以前的资源包。
本修复包不含原完整资源或用户数据库。Run_TOEO_Local.cmd 保留旧森林入口。

恢复依据和限制
河口商人位置、11 件商品及购价沿用同地区历史 Wiki 存档。地图名称是原小地图与史料
的视觉对应推断；商人官方实体 ID、模型和道具 master 编号尚未恢复。
https://www.wikihouse.com/toeowiki/index.php?%C5%B9#u392bcdb
恢复量按历史消耗品页：柠檬 HP300、鲔鱼 HP500、菠萝 TP100、混合 HP50/TP20，
不超过当前上限；满值且无收益、未知效果或错误目标时保留物品。
https://www.wikihouse.com/toeowiki/index.php?%A5%A2%A5%A4%A5%C6%A5%E0/%BE%C3%CC%D7%C9%CA
5000 初始金币、20 堆叠、32 格、半价回收、Lv1 最大 HP100/TP30 是暂定离线规则。
当前河口只开放 178 个保守通行单元；装备、战斗、咏唱中断、增益复活、经验升级、
主支线任务、出口换图及其他地图/NPC 仍需继续恢复。
53 项本地检查通过，112 个源文件与被测 Git 提交一致；实际 Windows 结果另存。
具体入口、证据与下一步见 NEXT_RECOVERY_V16.txt 和 RELEASE_METADATA.json。
'''
 (root/'README_CN.txt').write_text(readme,encoding='utf-8')
 state=f'''永恒传说 Online 当前恢复状态 v16（2026-10-10）

原客户端实机验证：原 HP/TP 栏显示、两件物品拖动交换及重启后的背包顺序恢复。
连贯流程包括地图进入、史料商人、原生买卖、右键详情、使用软糖和关店行走。
Windows run：{proof['windows_run_id']}；artifact：{proof['artifact_id']}。
被测提交：{proof['tested_commit']}。
Artifact SHA256：{proof['artifact_sha256']}。
53 项本地检查、112 文件 Git blob 对照通过；原图和机码证据在 evidence。

实际测试：5000 金币买柠檬软糖 3 个及混合软糖 1 个，每个 360，余额 3560；
卖柠檬 1 个后 3740；自选目标双击使用柠檬，数量 2→1、测试 HP40→100、TP10 不变。
拖动交换后，混合软糖在第 1 格，柠檬在第 2 格，各 1 个。重启原端和本地服务后，
顺序、金币 3740、HP100/TP10 和位置恢复一致。
HP40/TP10 只用于隔离验收存档；交付不含数据库，新角色仍从满 HP100/TP30 开始。

血条根因已从生命值包问题收敛到图形兼容：原控件数值正确、FVF 和顶点正常，
512×256 的 D3DFMT_P8（41）纹理实际 DrawPrimitiveUP 返回 8876086C。
预验证开关原本为 0，ValidateDevice 根因假设已排除并保留纠正记录。
现在仅在独立运行目录展开四张原调色板 TGA，532480 个像素的颜色、透明度和方向
均通过独立解码核对。原端加载 32 位 A8R8G8B8（21），真实绘图成功并复核画面。
原 EXE、原资源、绘图返回值和角色内存没有被替换或伪造。

背包是原生连续列表，不是任意空洞的固定 32 槽。新增 54 移动请求、67/6B 回执、
持久化顺序、全堆交换/移到末尾、售空/耗尽补位、旧库迁移与事务重放保护。
重启原 34/6B 解码调用 GUI 插入参数 -1，应检查原链表实际顺序，不能误判成第 -1 格。
装备卸下同样调用 4F6BA0 的 54，源位置类型 4；背包类型 2。装备功能仍待接入。

河口地图 0x1120108，史料商人格子 (141,313)，11 件商品，178 个保守通行单元。
商人官方模型/实例、官方物品 master、Lv1 数值和完整碰撞仍未恢复。
装备、战斗、咏唱中断、增益复活、经验升级、主支线任务和出口换图尚未完成。
继续使用原资源及用户存档；隔离分支 adaierk/glb / toeo-local-world-recovery-20261009。
原 ToEO_CL.dat SHA256：{proof['original_binary_sha256']}。
'''
 (root/'TOEO_RESTORATION_CURRENT_STATE.txt').write_text(state,encoding='utf-8')

if __name__=='__main__':main()
