from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json

from agent.service import AgentService


@require_GET
def health_mcp(_request):
    service = AgentService()
    health = service.check_connectivity()
    return JsonResponse({"ok": health["ok"], "details": health["details"]})


@csrf_exempt
@require_POST
def agent_query(request):
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        payload = json.loads(request.body or b"{}")
        query = payload.get("query", "")
        scenario = payload.get("scenario", "generic")
        
        logger.info(f"Received query request: {query[:100]}...")
        
        service = AgentService()
        result = service.handle_query(query=query, scenario=scenario)
        
        logger.info(f"Query completed. Summary length: {len(result.get('summary', ''))}, Citations: {len(result.get('citations', []))}")
        
        return JsonResponse(result)
    except Exception as e:
        logger.error(f"Error in agent_query view: {e}", exc_info=True)
        return JsonResponse({
            "error": str(e),
            "query": payload.get("query", "") if 'payload' in locals() else "",
            "citations": []
        }, status=500)




