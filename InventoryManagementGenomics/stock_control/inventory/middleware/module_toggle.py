from stock_control.module_loader import module_flags


class ModuleToggleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.module_config = module_flags()
        return self.get_response(request)
