def title(t):
    return f"[B][LOWERCASE][CAPITALIZE][COLOR white]{t}[/CAPITALIZE][/LOWERCASE][/B][/COLOR]"

def channel_title(t):
    return f"[B][LOWERCASE][CAPITALIZE][COLOR white]{t}[/CAPITALIZE][/LOWERCASE][/B][/COLOR]"

def programs_title(t):
    return f"[B][LOWERCASE][CAPITALIZE][COLOR white]{t}[/CAPITALIZE][/LOWERCASE][/B][/COLOR]"

def seasons_title(t):
    return f"[B][LOWERCASE][CAPITALIZE][COLOR white]{t}[/CAPITALIZE][/LOWERCASE][/B][/COLOR]"

def collections_title(t):
    return f"[B][LOWERCASE][CAPITALIZE][COLOR white]{t}[/CAPITALIZE][/LOWERCASE][/B][/COLOR]"

def episodes_title(t):
    return f"[B][LOWERCASE][CAPITALIZE][COLOR white]{t}[/CAPITALIZE][/LOWERCASE][/B][/COLOR]"

def episodes_plot(description, aired=None, duration=None, rating=None):
    meta = []
    if aired:
        meta.append(f"[COLOR yellow]{aired}[/COLOR]")
    if duration:
        meta.append(f"[COLOR yellow]{duration}[/COLOR]")
    if rating:
        meta.append(f"[COLOR orange]+{rating}[/COLOR]")

    if not meta:
        return description or ""
    return "  |  ".join(meta) + f"\n\n{description or ''}"

def nextPage(n):
    return f"[B][LOWERCASE][CAPITALIZE][COLOR lime] go to page {n}[/CAPITALIZE][/LOWERCASE][/B][/COLOR]"