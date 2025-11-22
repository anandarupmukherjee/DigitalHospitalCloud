from stock_control.module_loader import module_flags as get_module_flags


def module_flags(request):
    flags = get_module_flags()
    return {"module_flags": flags, "flags": flags}
