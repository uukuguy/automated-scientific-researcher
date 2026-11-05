"""Fold pinned pi system deltas for comparison with its compacted snapshot.

Source records remain unchanged. This is equality of effective configuration,
not permission to accept a new tool definition or to discard original deltas.
"""
import json


def effective_system_context(rows):
    content=[];sections={};tools={}
    for row in rows:
        if row['role']!='system':continue
        message=json.loads(row['text'])
        if set(message)-{'role','content','sections','toolsAdded','toolsRemoved'}:raise ValueError('unsupported_system_context')
        value=message['content']
        if isinstance(value,list):
            if any(set(v)!={'type','text'} or v['type']!='text' for v in value):raise ValueError('unsupported_system_content')
            value='\n'.join(v['text'] for v in value)
        if type(value) is not str:raise ValueError('unsupported_system_content')
        if value:content.append(value)
        for key,value in message.get('sections',{}).items():
            if value is None:sections.pop(key,None)
            else:sections[key]=value
        for tool in message.get('toolsRemoved',[]):tools.pop(tool['name'],None)
        for tool in message.get('toolsAdded',[]):tools[tool['name']]=tool
    return dict(content='\n\n'.join(content),sections=sections,tools=list(tools.values()))
