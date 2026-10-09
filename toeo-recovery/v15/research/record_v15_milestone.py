"""Gate the v15 release on actual Windows mouse use and service/client restart."""
import argparse,hashlib,json,sqlite3
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True)
    p.add_argument('--tested-commit',required=True);p.add_argument('--workflow-run',type=int,required=True)
    p.add_argument('--artifact',type=int,required=True);p.add_argument('--visual-reviewed',action='store_true')
    a=p.parse_args();root=Path(__file__).resolve().parent;folder=root/'new_evidence'/f'windows_run{a.run}'
    phases=('first','reentered');results={phase:json.loads((folder/phase/'runtime_result.json').read_text()) for phase in phases}
    logs={phase:{n:[json.loads(l) for l in (folder/phase/(n+'.jsonl')).read_text().splitlines()] for n in ('server','runtime')} for phase in phases}
    first,second=results['first'],results['reentered']
    checks=('map_entered','npc_selected_native','shop_catalog_parsed_native','shop_frame_shown_native',
        'shop_historical_names_native','shop_historical_prices_native','shop_historical_item_count_native',
        'historical_merchant_position_native','historical_map_id_native','shop_closed_native','movement_after_shop_close_native',
        'buy_request_built_native','sell_request_built_native','buy_money_quantity_native','sell_money_quantity_native',
        'shop_quantity_refreshed_native','inventory_window_open_native','original_lemon_icon_native','item_used_native','hp_recovered_native')
    assert all(first[k] is True for k in checks),{k:first[k] for k in checks if first[k] is not True}
    restart=('map_entered','position_restored_without_movement','inventory_restored_native','vitals_restored_native','inventory_window_open_native','original_lemon_icon_native')
    assert all(second[k] is True for k in restart),{k:second[k] for k in restart if second[k] is not True}
    uses=[e for e in logs['first']['server'] if e.get('event')=='item_use_committed' and not e['replayed']]
    assert len(uses)==1 and uses[0]['snapshot']['items'][0]['quantity']==1 and uses[0]['vitals']['hp']==100
    assert uses[0]['snapshot']['money']==4100 and uses[0]['vitals']['tp']==10
    assert any(e.get('event')=='item_source_sent' and e.get('compressed') for e in logs['first']['server'])
    assert any(e.get('event')=='shop_close_command_ack' and e.get('sequence')==3 for e in logs['first']['server'])
    assert any(e.get('event')=='native_item_use_builder_enter' and e.get('pending')=='0x0' and e.get('sequence_before')==3 for e in logs['first']['runtime'])
    assert uses[0]['sequence']==4
    assert uses[0]['target']==[1,1]
    assert any(e.get('event')=='native_actor_target_set' and e.get('target')==[1,1] for e in logs['first']['runtime'])
    assert any(e.get('event')=='native_item_source_reply_leave' for e in logs['first']['runtime'])
    assert any(e.get('event')=='native_inventory_ui_item' and e.get('quantity')==1 and e.get('icon_id')==3811 for e in logs['reentered']['runtime'])
    for phase in phases:
        assert not any(e.get('event')=='frida_error' for e in logs[phase]['runtime'])
        assert not any(e.get('event')=='protocol_rejected' for e in logs[phase]['server'])
    assert not any(e.get('event') in ('item_use_committed','shop_trade_committed') for e in logs['reentered']['server'])
    with sqlite3.connect(folder/'first/local_accounts.sqlite') as db:
        items=db.execute('SELECT name,quantity FROM world_inventory_items').fetchall()
        vitals=db.execute('SELECT hp,tp,max_hp,max_tp FROM world_vitals').fetchall()
        ledger=db.execute('SELECT opcode,sequence FROM world_trade_ledger ORDER BY id').fetchall()
    assert items==[('レモングミ',1)] and vitals==[(100,10,100,30)]
    assert [row[0] for row in ledger]==[0xde,0xdf,0x55]
    assert a.visual_reviewed,'Review actual native desktop captures before delivery'
    proof={'passed':True,'run':a.run,'tested_commit':a.tested_commit,'windows_run_id':a.workflow_run,'artifact_id':a.artifact,
        'artifact_sha256':hashlib.sha256(folder.with_suffix('.zip').read_bytes()).hexdigest(),
        'checks':{k:first[k] for k in checks},'restart_checks':{k:second[k] for k in restart},'native_uses':uses,
        'visual_reviewed':True,'saved_inventory':first['saved_inventory'],'saved_vitals':first['saved_vitals'],
        'database_items':items,'database_vitals':vitals,'database_ledger':ledger,'final_pixel':first['observed_positions'][-1],
        'local_checks_passed':45,'source_files_verified':107,'complete_gameplay':False,
        'original_binary_sha256':'635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55',
        'test_fixture':'Only isolated CI save begins HP40/TP10; fresh delivery starts full HP100/TP30',
        'icon_provenance':'Original ICND lookup verified; item-name associations visually matched, not official item-master IDs',
        'limitations':['HP/TP HUD numeric/bar rendering still incomplete','Casting, interrupted use, buffs, revival and battle targeting pending',
            'Equipment, combat, quests, map transitions and complete collision pending','Provisional local level-one stat limits, wallet and stack rules']}
    (root/'new_evidence/auth/v15_actual_item_use_milestone.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    state=f'''永恒传说 Online 当前恢复状态 v15（2026-10-10，北京时间）

原Windows客户端本轮已通过地图进入、史料商人、购买/出售、原图标、右键详情、
真实鼠标软糖使用、背包扣1、HP更新，以及原端和本地服务重启后的恢复检查。
RUN{a.run}：{a.workflow_run}；artifact：{a.artifact}。
测试提交：{a.tested_commit}。隔离分支adaierk/glb / toeo-local-world-recovery-20261009。
Artifact SHA256：{proof['artifact_sha256']}。
证据：v15_actual_item_use_milestone.json、v15_source_consistency.json、原Windows桌面和协议记录。
45项本地检查通过；107源文件与被测Git提交的blob逐字节一致。

实际流程：5000金币买3个レモングミ，每个360，余额3920；卖1个后余额4100、数量2；
右键取得原道具详情；实际双击使用1个，数量1，测试HP40→100，TP保留10。
该测试存档预先设定HP40/TP10以验证恢复；交付用户的新角色仍是满100/30。
重启原端和服务后仍是4100金币、柠檬软糖1个、HP100/TP10，位置恢复一致。

重要纠正：v14误称的item+30模板指针实际上是全局图标整数。ITEM组原起始3805，
柠檬偏移6，原图标3811；原服官方物品master编号仍未找回，商品名与图案为视觉关联。
Run54右键断线的原因已定位为压缩ED被旧解码器拒绝，不是已证明的空模板问题。
现在支持原CNLzComp1压缩包装和CRC，原622960/622AC0交叉验证通过，ED→EE详情已接入。
补上原商店关闭E0的67回执，避免共享命令队列一直等待、拦截后续55使用请求。
55使用请求、67/6B扣数量与B2 HP/TP更新由原客户端构建/解码；新增Frida仅只读观察。
world_vitals与扣物品同一次SQLite事务保存，重放不再扣物品，失败回滚，删角色也清理生命值。

河口地图0x1120108，行商人＜道具屋＞格子(141,313)，同地区11件史料商品。
地图地名仍是原小地图与Wiki的视觉对应推断。商人官方实体ID/模型未恢复，暂用本地选择。
本轮恢复原软糖、红草图标；三种瓶类图标未识别。当前河口开放178个保守通行单元。
5000初始金币、20堆叠、32格、半价回收、Lv1最大HP100/TP30均为明确暂定离线规则。
恢复量按TOEO历史消耗品Wiki存档；柠檬4秒咏唱及受击中断、增益、复活和战斗目标尚未实现。
HP/TP数据更新已经验证，但左上HP/TP栏的原显示仍需修复。完整游戏尚未完成。

启动：Run_TOEO_Rashuan.cmd；旧森林入口Run_TOEO_Local.cmd。
沿用完整原资源包，升级复制local_world_userdata，账号archive001 / local123。
原ToEO_CL.dat不改，SHA256：{proof['original_binary_sha256']}。
NEXT_RECOVERY_V15.txt记录全部原机码入口和接续事项；旧状态保存在history。
下一阶段优先HP/TP原UI和道具咏唱，再装备、战斗、换图和主支线任务。
'''
    (root/'TOEO_RESTORATION_CURRENT_STATE.txt').write_text(state,encoding='utf-8')
    print(json.dumps({'passed':True,'quantity_after_use':1,'hp':100,'tp':10,'money':4100,'restart_verified':True}))


if __name__=='__main__':main()
