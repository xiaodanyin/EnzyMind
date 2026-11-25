"""n8n's native NDJSON stream: visible Agent text and a final memory envelope."""
import json


async def read_workflow_response(response, on_text):
    # aiter_lines handles arbitrary transport boundaries and split UTF-8 bytes.
    pending = ''
    async for line in response.aiter_lines():
        if not line.strip():
            continue
        pending += line + '\n'
        if len(pending) > 2_000_000:
            raise ValueError('The workflow response exceeded its size limit.')
        try:
            frame = json.loads(pending)
        except ValueError:
            continue  # Legacy pretty-printed JSON, or a malformed frame at EOF.
        pending = ''
        if isinstance(frame, list) and len(frame) == 1:
            frame = frame[0]
        if not isinstance(frame, dict):
            raise ValueError('The workflow returned an invalid response.')
        if 'type' not in frame:
            # Compatibility while the workflow and gateway roll out separately.
            return frame
        if frame['type'] == 'error':
            raise ValueError('The workflow stream failed. Saved results remain available.')
        node = (frame.get('metadata') or {}).get('nodeName')
        if frame['type'] == 'item' and node == 'Research Agent':
            if isinstance(frame.get('content'), str):
                on_text(frame['content'])
        elif frame['type'] == 'item' and node == 'Workspace response':
            content = frame.get('content')
            if isinstance(content, str):
                content = json.loads(content)
            if isinstance(content, dict):
                return content
            raise ValueError('The workflow returned an invalid completion record.')
        # Never expose memory compression, tool arguments or other node output.
        # The Agent's end frame alone is NOT a completed memory transaction.
    raise ValueError('The answer stream ended before completion. Partial text and saved results are preserved; memory was not changed.')
