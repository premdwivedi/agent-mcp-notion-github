from django.urls import path
from .views import health_mcp, agent_query

urlpatterns = [
    path("health/mcp", health_mcp, name="health_mcp"),
    path("agent/query", agent_query, name="agent_query"),
]




