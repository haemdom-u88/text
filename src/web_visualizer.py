"""
Web可视化数据准备器
"""
import json
from collections import defaultdict
import networkx as nx
from datetime import datetime

class WebVisualizer:
    def __init__(self):
        self.color_map = {
            'PERSON': '#FF6B6B',
            'ORGANIZATION': '#4ECDC4',
            'LOCATION': '#45B7D1',
            'EVENT': '#96CEB4',
            'DATE': '#FFEAA7',
            'PRODUCT': '#DDA0DD',
            'CONCEPT': '#98D8C8',
            'DISEASE': '#F7DC6F',
            'default': '#95A5A6'
        }
    
    def prepare_visualization_data(self, extracted_data, graph_data):
        """准备可视化数据"""
        result = {
            'graph': self._prepare_graph_data(extracted_data, graph_data),
            'entities': self._prepare_entity_data(extracted_data),
            'relations': self._prepare_relation_data(extracted_data),
            'timeline': self._prepare_timeline_data(extracted_data),
            'statistics': self._prepare_statistics(extracted_data)
        }
        
        return result
    
    def _prepare_graph_data(self, extracted_data, graph_data):
        """准备知识图谱数据（ECharts格式）"""
        nodes = []
        links = []
        node_set = set()

        # 首先尝试使用 graph_data 中的节点（来自 kg_builder.build），更可靠
        gd_nodes = (graph_data or {}).get('nodes', [])
        for n in gd_nodes:
            entity_id = n.get('id') or n.get('name', '')
            if entity_id and entity_id not in node_set:
                nodes.append({
                    'id': entity_id,
                    'name': n.get('name', ''),
                    'category': n.get('type', ''),
                    'symbolSize': n.get('symbolSize', 30),
                    'value': n.get('name', ''),
                    'label': n.get('label', {'show': True, 'position': 'right'}),
                    'itemStyle': {
                        'color': self.color_map.get(n.get('type', ''), self.color_map['default'])
                    }
                })
                node_set.add(entity_id)

        # 使用 graph_data 中的边（如果存在）
        gd_edges = (graph_data or {}).get('edges', [])
        for i, e in enumerate(gd_edges):
            source = e.get('source')
            target = e.get('target')
            relation_name = e.get('relation', '')
            if source and target and source in node_set and target in node_set:
                links.append({
                    'id': f'link_{i}',
                    'source': source,
                    'target': target,
                    'value': relation_name,
                    'label': {
                        'show': True,
                        'formatter': relation_name,
                        'position': 'middle'
                    },
                    'lineStyle': {
                        'width': 2,
                        'curveness': 0.2
                    }
                })

        # 若 graph_data 没有边，则兼容 extracted_data 中的多种格式（dict 或 list）
        if not links:
            entities = extracted_data.get('entities', [])
            relations = extracted_data.get('relations', [])
            for entity in entities:
                eid = entity.get('id', entity.get('name', ''))
                if eid and eid not in node_set:
                    nodes.append({
                        'id': eid,
                        'name': entity.get('name', ''),
                        'category': entity.get('type', ''),
                        'symbolSize': 30,
                        'value': entity.get('name', ''),
                        'label': {'show': True, 'position': 'right'},
                        'itemStyle': {'color': self.color_map.get(entity.get('type', ''), self.color_map['default'])}
                    })
                    node_set.add(eid)

            for i, relation in enumerate(relations):
                if isinstance(relation, dict):
                    source = relation.get('subject')
                    target = relation.get('object')
                    relation_name = relation.get('relation', '')
                elif isinstance(relation, (list, tuple)) and len(relation) >= 3:
                    source, relation_name, target = relation[0], relation[1], relation[2]
                else:
                    continue

                if source in node_set and target in node_set:
                    links.append({
                        'id': f'link_fallback_{i}',
                        'source': source,
                        'target': target,
                        'value': relation_name,
                        'label': {'show': True, 'formatter': relation_name, 'position': 'middle'},
                        'lineStyle': {'width': 2, 'curveness': 0.2}
                    })

        # categories 以提取结果中的实体类型为准
        return {
            'nodes': nodes,
            'links': links,
            'categories': self._get_categories(extracted_data.get('entities', []))
        }
    
    def _prepare_entity_data(self, extracted_data):
        """准备实体数据"""
        entities = extracted_data.get('entities', [])
        
        # 按类型分组
        entities_by_type = defaultdict(list)
        for entity in entities:
            entity_type = entity.get('type', '其他')
            entities_by_type[entity_type].append({
                'name': entity.get('name', ''),
                'id': entity.get('id', ''),
                'confidence': entity.get('confidence', 1.0)
            })
        
        # 统计每个类型的数量
        type_stats = []
        for entity_type, items in entities_by_type.items():
            type_stats.append({
                'type': entity_type,
                'count': len(items),
                'color': self.color_map.get(entity_type, self.color_map['default'])
            })
        
        return {
            'list': entities,
            'by_type': dict(entities_by_type),
            'type_stats': type_stats,
            'total_count': len(entities)
        }
    
    def _prepare_relation_data(self, extracted_data):
        """准备关系数据"""
        relations = extracted_data.get('relations', [])

        # 统计关系类型，兼容字典格式和列表/元组格式
        relation_counts = defaultdict(int)
        normalized_relations = []

        for rel in relations:
            rel_type = None
            subj = None
            obj = None

            if isinstance(rel, dict):
                subj = rel.get('subject') or rel.get('s')
                obj = rel.get('object') or rel.get('o')
                rel_type = rel.get('relation') or rel.get('relation_type') or rel.get('type')
                normalized_relations.append({'subject': subj, 'relation': rel_type, 'object': obj})
            elif isinstance(rel, (list, tuple)):
                # 常见格式 [subject, relation, object]
                if len(rel) >= 3:
                    subj, rel_type, obj = rel[0], rel[1], rel[2]
                    normalized_relations.append({'subject': subj, 'relation': rel_type, 'object': obj})
                elif len(rel) == 2:
                    # [subject, object]（relation类型未知）
                    subj, obj = rel[0], rel[1]
                    normalized_relations.append({'subject': subj, 'relation': None, 'object': obj})
                else:
                    # 无效格式，跳过
                    continue
            else:
                # 非法格式，跳过
                continue

            if rel_type:
                relation_counts[rel_type] += 1

        return {
            'list': normalized_relations,
            'type_counts': dict(relation_counts),
            'total_count': len(normalized_relations)
        }
    
    def _prepare_timeline_data(self, extracted_data):
        """准备时间线数据"""
        timeline_events = extracted_data.get('events', [])
        events = []
        
        for event in timeline_events:
            if isinstance(event, dict):
                events.append({
                    'time': event.get('time', ''),
                    'content': event.get('content', ''),
                    'entities': event.get('entities', [])
                })
        
        return {
            'events': events,
            'event_count': len(events)
        }
    
    def _prepare_statistics(self, extracted_data):
        """准备统计数据"""
        return {
            'entity_count': len(extracted_data.get('entities', [])),
            'relation_count': len(extracted_data.get('relations', [])),
            'event_count': len(extracted_data.get('events', [])),
            'extraction_time': datetime.now().isoformat()
        }
    
    def _get_categories(self, entities):
        """获取实体类别"""
        categories = set()
        for entity in entities:
            entity_type = entity.get('type', '')
            if entity_type:
                categories.add(entity_type)
        
        return [{
            'name': cat,
            'itemStyle': {
                'color': self.color_map.get(cat, self.color_map['default'])
            }
        } for cat in categories]