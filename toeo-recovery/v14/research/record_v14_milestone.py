"""Require actual original Windows trades and restart before v14 release."""
import argparse,hashlib,json,sqlite3
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True)
    p.add_argument('--tested-commit',required=True);p.add_argument('--workflow-run',type=int,required=True)
    p.add_argument('--artifact',type=int,required=True);p.add_argument('--visual-reviewed',action='store_true')
    a=p.parse_args();root=Path(__file__).resolve().parent;folder=root/'new_evidence'/f'windows_run{a.run}'
    results={phase:json.loads((folder/phase/'runtime_result.json').read_text()) for phase in ('first','reentered')}
    logs={phase:{n:[json.loads(l) for l in (folder/phase/(n+'.jsonl')).read_text().splitlines()] for n in ('server','runtime')}
          for phase in ('first','reentered')}
    first,second=results['first'],results['reentered']
    checks=('map_entered','npc_selected_native','shop_catalog_parsed_native','shop_frame_shown_native',
            'shop_historical_names_native','shop_historical_prices_native','shop_historical_item_count_native',
            'historical_merchant_position_native','historical_map_id_native','shop_closed_native',
            'movement_after_shop_close_native','buy_request_built_native','sell_request_built_native',
            'buy_money_quantity_native','sell_money_quantity_native','shop_quantity_refreshed_native','inventory_window_open_native')
    assert all(first[k] is True for k in checks),{k:first[k] for k in checks if first[k] is not True}
    assert second['map_entered'] and second['position_restored_without_movement'] and second['inventory_restored_native']
    assert second['inventory_window_open_native']
    trades=[e for e in logs['first']['server'] if e.get('event')=='shop_trade_committed' and not e['replayed']]
    assert [e['opcode'] for e in trades]==[0xde,0xdf]
    assert [(e['snapshot']['money'],e['snapshot']['items'][0]['quantity']) for e in trades]==[(3920,3),(4100,2)]
    for phase in logs:
        assert not any(e.get('event')=='frida_error' for e in logs[phase]['runtime'])
    assert any(e.get('event')=='native_trade_reply_leave' and e.get('pending')=='0x0' and e.get('applied_sequence')==2 for e in logs['first']['runtime'])
    assert any(e.get('event')=='native_inventory_ui_item' and e.get('quantity')==2 for e in logs['first']['runtime'])
    assert any(e.get('event')=='native_inventory_ui_item' and e.get('quantity')==2 for e in logs['reentered']['runtime'])
    assert not any(e.get('event')=='shop_trade_committed' for e in logs['reentered']['server'])
    with sqlite3.connect(folder/'first/local_accounts.sqlite') as db:
        wallets=db.execute('SELECT character_id,account_id,money FROM world_wallets').fetchall()
        items=db.execute('SELECT character_id,account_id,name,quantity,buy_price,sell_price FROM world_inventory_items').fetchall()
        ledger=db.execute('SELECT opcode,sequence FROM world_trade_ledger ORDER BY id').fetchall()
    assert wallets==[(1,1,4100)] and items==[(1,1,'レモングミ',2,360,180)] and ledger==[(0xde,1),(0xdf,2)]
    assert a.visual_reviewed,'Inspect actual game pixels before claiming visible inventory success'
    proof={'passed':True,'tested_commit':a.tested_commit,'windows_run_id':a.workflow_run,'artifact_id':a.artifact,
        'artifact_sha256':hashlib.sha256(folder.with_suffix('.zip').read_bytes()).hexdigest(),
        'run':a.run,'checks':{k:first[k] for k in checks},'native_trades':trades,
        'inventory_and_wallet_restored_native':True,'visual_reviewed':True,'database_wallets':wallets,
        'database_items':items,'database_ledger':ledger,'saved_inventory':first['saved_inventory'],
        'reentry_saved_inventory':second['saved_inventory'],'final_pixel':first['observed_positions'][-1],
        'original_binary_sha256':'635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55',
        'local_checks_passed':38,'original_item_templates_icons_verified':False,'complete_gameplay':False,
        'offline_rules':{'initial_money_once_per_character':5000,'stack_limit':20,'bag_capacity':32,'resale':'half of purchase price rounded down',
                         'provenance':'Provisional local recovery rules; official initial grant/stack/resale values unresolved'},
        'scope':'Actual Windows original executable, real mouse controls, unchanged original parsers/renderer, localhost server and restart',
        'limitations':['Original item templates/icons and use effects unresolved','Right-click item details remain unresolved; Run45 recorded original-client disconnection',
                       'Combat, equipment, quests, map transitions and full collision pending',
                       'Merchant native identity/model provisional; placement/name/stock sourced as in v13','Original resource/UI exception logs retained']}
    (root/'new_evidence/auth/v14_actual_trade_milestone.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    state=f'''永恒传说 Online 当前恢复状态 v14（2026-10-09）

最终原Windows客户端购买、出售、物品窗口、关闭商店、行走与重启检查均通过。
测试代码提交：{a.tested_commit}
Windows RUN{a.run}：{a.workflow_run}；artifact：{a.artifact}。
Artifact SHA256：{proof['artifact_sha256']}
隔离分支：adaierk/glb / toeo-local-world-recovery-20261009。
证据：evidence/native/v14_actual_trade_milestone.json、v14_source_consistency.json，
以及evidence/windows_run{a.run}/first和reentered。截图已人工核对原游戏像素。

实际原端交易
初始5000，买3个レモングミ（购价360），余额3920、持有3个。
卖出1个（暂定回收价180），余额4100、持有2个；原商店即时显示新数量。
购买DE/出售DF由原4F8050/4F81B0构包。保留发送层改写的线上请求号。
67回执解除原挂起请求，50更新原校验钱包，36..3D和4D/4C更新物品及可见商店。
6B完整通知同步背包；初次及重登入图34均恢复持久化金币和物品。
真实鼠标打开原物品窗口，565210只读观察确认窗口可见与数量2。
未替换游戏界面、物品名称解码、数量解码或原渲染逻辑。

持久化与校验
world_wallets、world_inventory_items、world_trade_ledger按角色保存。
一次SQLite事务完成订单；失败回滚，重复请求不重复交易，拒绝越权和超量出售。
重启原端及本地服务后仍是4100金币、レモングミ2个；地图位置也恢复一致。
删角色清理交易、物品、金币和位置。交付不含用户数据库。
38项本地检查通过；原机码构包、背包名称/数量、钱包校验、67/6B处理、
4D原物品克隆与刷新、4C售空删除通过。97个源文件与被测Git版本逐字节一致。

商人与史料
地图0x1120108，ラシュアン河の河口。地名由原小地图和Wiki地名图像对照推断。
行商人＜道具屋＞：grid(141,313)，pixel(4544,5024)。11件商品购价沿用同地区史料。
https://www.wikihouse.com/toeowiki/index.php?%C5%B9#u392bcdb
历史库13组商店、140条商品、6组明确XY；仅1组完成定位并部署。
NPC原官方实体编号与模型未找回，目前使用本地选择。
河口只开放码头178个保守通行单元；森林与河口位置分别保存。

明确暂定的离线规则
初始金币5000（每角色一次）、单种20个堆叠、32格、回收购价一半。
这些规则尚无可靠原服史料，不能当作官方机制。原钱包上限10000000。

启动与下一阶段
Run_TOEO_Rashuan.cmd进入河口；Run_TOEO_Local.cmd保留旧森林入口。
沿用完整原资源包，升级复制local_world_userdata，账号archive001 / local123。
ToEO_CL.dat不修改，SHA256：
{proof['original_binary_sha256']}。
原道具模板/图标/使用效果、装备、战斗、任务、完整碰撞与换图尚未完成。
物品右键详情曾触发原端断线，左键购物车为本版已验证操作。
原资源/UI异常及HP/TP数值仍待恢复，完整游玩流程尚未完成。
下一阶段优先恢复原ITEM模板及图标映射，再接道具使用、HP/TP效果与战斗。
NEXT_RECOVERY_V14.txt保留接续入口和失败记录，旧v13状态保存在history中。
'''
    (root/'TOEO_RESTORATION_CURRENT_STATE.txt').write_text(state,encoding='utf-8')
    print(json.dumps({'passed':True,'buy_money':3920,'sell_money':4100,'saved_quantity':2,'restart_verified':True}))


if __name__=='__main__':main()
