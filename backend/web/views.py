from inertia import render
from django.http import HttpRequest


def home(request: HttpRequest):
    return render(request, "Chat", props={"title": "MCP Agent Chat"})




