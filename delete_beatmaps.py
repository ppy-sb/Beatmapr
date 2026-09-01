# delete_beatmaps.py
from beatmapr.app.database import SessionLocal
from beatmapr.app.models import Pack, Beatmap, PackBeatmap

def main():
    session = SessionLocal()
    try:
        # 1. 查找曲包 S1691
        pack = session.query(Pack).filter(Pack.slug == "S1691").first()
        if not pack:
            print("曲包 S1691 不存在！")
            return

        print(f"找到曲包: {pack.name} (ID: {pack.id})")

        # 2. 你要删除的 beatmap_id 列表
        target_ids = [5191205, 5256490, 5256508, 5257838]

        # 3. 仅从该曲包中移除关联（不删除 Beatmap 本身）—— 安全做法
        deleted_count = session.query(PackBeatmap).filter(
            PackBeatmap.pack_id == pack.id,
            PackBeatmap.beatmap_id.in_(target_ids)
        ).delete(synchronize_session=False)

        print(f"已从曲包中移除 {deleted_count} 个谱面关联")

        # （可选）如果确定要彻底删除 Beatmap，取消下面注释
        # 但必须确保这些谱面不被其他曲包引用！
        # session.query(Beatmap).filter(Beatmap.beatmap_id.in_(target_ids)).delete(synchronize_session=False)

        session.commit()
        print("操作成功！")

    except Exception as e:
        session.rollback()
        print(f"操作失败，已回滚: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    main()