"""
最小评估脚本：计算 Precision / Recall / F1（实体与关系）
用法：
  python tools/eval_f1.py --pred path/to/pred.json --gold data/gold_sample.json

JSON 格式要求：
{
  "entities": [{"id"|"name", "type": ...}, ...],
  "relations": [{"source", "target", "relation"|"type"}, ...]
}

判定规则（简单精确匹配）：
- 实体：匹配 key = (name_or_id, type)
- 关系：匹配 key = (source, relation, target)

你可以根据需要在此脚本中定制“宽松匹配”（例如忽略大小写、同义词映射）。
"""
import json
import argparse
from typing import Tuple, Set


def load(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def unwrap_payload(payload: dict) -> dict:
    """兼容常见返回结构：data.extracted / extracted / entities&relations / nodes&edges。"""
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get('data'), dict) and isinstance(payload['data'].get('extracted'), dict):
        return payload['data']['extracted']
    if isinstance(payload.get('extracted'), dict):
        return payload['extracted']
    if 'entities' in payload or 'relations' in payload:
        return payload
    if 'nodes' in payload or 'edges' in payload:
        return payload
    return payload


def normalize(token: str, ignore_case=False, strip_symbols=False) -> str:
    if token is None:
        token = ''
    token = token.strip()
    if ignore_case:
        token = token.lower()
    if strip_symbols:
        token = token.replace('_', ' ').replace('-', ' ')
        token = ' '.join(token.split())
    return token


def entity_key(e, ignore_case=False, strip_symbols=False) -> Tuple[str, str]:
    name = e.get('name') or e.get('id') or e.get('label') or ''
    typ = e.get('type') or ''
    return (
        normalize(name, ignore_case, strip_symbols),
        normalize(typ, ignore_case, strip_symbols)
    )


def relation_key(r, ignore_case=False, strip_symbols=False) -> Tuple[str, str, str]:
    src = r.get('source') or r.get('s') or r.get('subject') or ''
    tgt = r.get('target') or r.get('o') or r.get('object') or ''
    rel = r.get('relation') or r.get('type') or ''
    return (
        normalize(src, ignore_case, strip_symbols),
        normalize(rel, ignore_case, strip_symbols),
        normalize(tgt, ignore_case, strip_symbols)
    )


def extract_entities_relations(payload: dict) -> Tuple[list, list]:
    """从 payload 中提取 entities / relations，支持 nodes/edges 格式。"""
    data = unwrap_payload(payload)
    entities = data.get('entities') or data.get('nodes') or []
    relations = data.get('relations') or data.get('edges') or []
    return entities, relations


def precision_recall_f1(pred_set: Set, gold_set: Set):
    tp = len(pred_set & gold_set)
    p = tp / len(pred_set) if pred_set else 0.0
    r = tp / len(gold_set) if gold_set else 0.0
    f1 = 0.0 if (p + r) == 0 else 2 * p * r / (p + r)
    return p, r, f1, tp


def main():
    ap = argparse.ArgumentParser(description='Compute Precision/Recall/F1 for entities and relations')
    ap.add_argument('--pred', required=True, help='预测结果 JSON 文件')
    ap.add_argument('--gold', required=True, help='金标准 JSON 文件')
    ap.add_argument('--ignore-case', action='store_true', help='忽略大小写匹配')
    ap.add_argument('--strip-symbols', action='store_true', help='规范化下划线/连字符为空格后再匹配')
    ap.add_argument('--report', help='将 FP/FN 详情输出到文件（json）')
    args = ap.parse_args()

    pred = load(args.pred)
    gold = load(args.gold)

    pred_entities_raw, pred_relations_raw = extract_entities_relations(pred)
    gold_entities_raw, gold_relations_raw = extract_entities_relations(gold)

    pred_entities = {entity_key(e, args.ignore_case, args.strip_symbols) for e in pred_entities_raw}
    gold_entities = {entity_key(e, args.ignore_case, args.strip_symbols) for e in gold_entities_raw}

    pred_relations = {relation_key(r, args.ignore_case, args.strip_symbols) for r in pred_relations_raw}
    gold_relations = {relation_key(r, args.ignore_case, args.strip_symbols) for r in gold_relations_raw}

    pe, re, f1e, tpe = precision_recall_f1(pred_entities, gold_entities)
    pr, rr, f1r, tpr = precision_recall_f1(pred_relations, gold_relations)

    print('=== Entities ===')
    print(f'Precision: {pe:.3f}, Recall: {re:.3f}, F1: {f1e:.3f}, TP: {tpe}, Pred: {len(pred_entities)}, Gold: {len(gold_entities)}')
    print('=== Relations ===')
    print(f'Precision: {pr:.3f}, Recall: {rr:.3f}, F1: {f1r:.3f}, TP: {tpr}, Pred: {len(pred_relations)}, Gold: {len(gold_relations)}')

    if args.report:
        report = {
            'entities': {
                'fp': sorted(list(pred_entities - gold_entities)),
                'fn': sorted(list(gold_entities - pred_entities))
            },
            'relations': {
                'fp': sorted(list(pred_relations - gold_relations)),
                'fn': sorted(list(gold_relations - pred_relations))
            }
        }
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f'Report written to {args.report}')


if __name__ == '__main__':
    main()
