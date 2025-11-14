from typing import Optional, Dict, Any, Tuple


def extract_ids_from_response_json(data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    从响应 JSON 中尽可能提取 `note_id` 与 `file_id` 等标识。

    解析策略（容错优先）：
    - 顶层 `note_id` 或 `id`
    - `note.id` 或 `data.note.id`
    - `attachments[0].id` 或 `attachments[0].file_id`

    返回值:
    - `(note_id, file_id, extra)`：若未找到对应字段则为 None，`extra` 保存可能的其他标识集合
    """
    note_id: Optional[str] = None
    file_id: Optional[str] = None
    extra: Dict[str, Any] = {}

    # 顶层常见字段
    for key in ("note_id", "id"):
        if isinstance(data.get(key), (str, int)):
            note_id = str(data[key])
            break

    # 嵌套 note 结构
    note_obj = None
    if isinstance(data.get("note"), dict):
        note_obj = data["note"]
    elif isinstance(data.get("data"), dict) and isinstance(data["data"].get("note"), dict):
        note_obj = data["data"]["note"]
    if note_obj and isinstance(note_obj.get("id"), (str, int)):
        note_id = note_id or str(note_obj["id"])

    # 附件结构
    attachments = None
    for key in ("attachments", "data"):
        val = data.get(key)
        if isinstance(val, list) and val:
            attachments = val
            break
        if isinstance(val, dict) and isinstance(val.get("attachments"), list):
            attachments = val["attachments"]
            break

    if attachments and isinstance(attachments[0], dict):
        att = attachments[0]
        if isinstance(att.get("id"), (str, int)):
            file_id = str(att["id"])
        elif isinstance(att.get("file_id"), (str, int)):
            file_id = str(att["file_id"])

    # 归档可能的其他标识
    for k in ("note", "attachments", "data"):
        if k in data:
            extra[k] = data[k]

    return note_id, file_id, extra

