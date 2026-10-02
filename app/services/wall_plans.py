"""Reusable, escaped SVG rendering of calculator-owned wall primitives."""
from html import escape


def render_wall_plan(layout, label, high_end='Right'):
    if not layout:
        return ''
    width, height = layout['width_mm'], layout['height_mm']
    font = max(width, height) / 45
    margin = font * 4
    mirrored = layout['stair'] and high_end == 'Left'
    title = f'{label} — wall layout' + (f' · high end {high_end.lower()}' if layout['stair'] else '')
    description = '; '.join(layout['summary'] + layout['notes'])
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" class="wall-plan-svg" role="img" aria-label="{escape(title, quote=True)}" '
           f'viewBox="{-margin:g} {-margin:g} {width + 2 * margin:g} {height + 2 * margin:g}" preserveAspectRatio="xMidYMid meet">',
           f'<title>{escape(title)}</title><desc>{escape(description)}</desc>']
    heading = label if len(label) <= 40 else label[:37] + '…'
    out.append(f'<text x="{width / 2:g}" y="{-font * 3:g}" font-family="sans-serif" font-size="{font:g}" text-anchor="middle" fill="#30312e">{escape(heading)}</text>')
    styles = {'wall': ('none', '#77796f'), 'mdf': ('#dce4bb', '#4b513f'),
              'opening': ('#ffffff', '#77796f'), 'bead': ('none', '#9b6b37'),
              'frame': ('none', '#695136'), 'dado': ('none', '#695136')}
    out.append(f'<g transform="translate(0 {height:g}) scale(1 -1)">')
    if mirrored:
        out.append(f'<g transform="translate({width:g} 0) scale(-1 1)">')
    for element in layout['elements']:
        kind = element['kind']
        fill, stroke = styles[kind]
        points = ' '.join(f'{x:g},{y:g}' for x, y in element['points'])
        tag = 'polyline' if kind in ('wall', 'dado') else 'polygon'
        provisional = element['provisional']
        dash = ' stroke-dasharray="6 4"' if provisional else ''
        out.append(f'<{tag} data-kind="{kind}" data-provisional="{str(provisional).lower()}" '
                   f'points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="{2 if kind in ("bead", "dado", "frame") else 1}" '
                   f'vector-effect="non-scaling-stroke"{dash}><title>{escape(element["label"])}</title></{tag}>')
    if mirrored:
        out.append('</g>')
    out.append('</g>')
    for element in layout['elements']:
        if element['provisional'] and element['kind'] in ('opening', 'frame', 'bead'):
            xs, ys = zip(*element['points'])
            tx, ty = (min(xs) + max(xs)) / 2, height - (min(ys) + max(ys)) / 2
            if mirrored:
                tx = width - tx
            out.append(f'<text x="{tx:g}" y="{ty:g}" font-family="sans-serif" font-size="{font * .7:g}" text-anchor="middle" fill="#30312e">'
                       f'<tspan x="{tx:g}">Trim to fit</tspan><tspan x="{tx:g}" dy="{font:g}">on site</tspan></text>')
    # Only display-space annotation placement lives here. Every measured endpoint
    # and value is already supplied by the calculator; labels are never mirrored.
    for dimension in layout['dimensions']:
        (x1, y1), (x2, y2) = dimension['start'], dimension['end']
        if mirrored:
            x1, x2 = width - x1, width - x2
        y1, y2 = height - y1, height - y2
        vertical = dimension['axis'] == 'vertical'
        if vertical:
            line = width + font * 1.5 if mirrored else -font * 1.5
            a, b = (line, y1), (line, y2)
            tx, ty = line + (-font if mirrored else font), (y1 + y2) / 2
            text_transform = f' transform="rotate(-90 {tx:g} {ty:g})"'
        else:
            line = height + font * 1.5 if y1 >= height else -font * 1.5
            a, b = (x1, line), (x2, line)
            tx, ty = (x1 + x2) / 2, line - font / 3
            text_transform = ''
        ax, ay = a; bx, by = b
        tick = font / 6
        out.append(f'<g stroke="#686b61" stroke-width="1" fill="none" vector-effect="non-scaling-stroke">'
                   f'<path d="M {x1:g} {y1:g} L {ax:g} {ay:g} M {x2:g} {y2:g} L {bx:g} {by:g} M {ax:g} {ay:g} L {bx:g} {by:g}"/>'
                   f'<path d="M {ax-tick:g} {ay-tick:g} L {ax+tick:g} {ay+tick:g} M {bx-tick:g} {by-tick:g} L {bx+tick:g} {by+tick:g}"/></g>'
                   f'<text x="{tx:g}" y="{ty:g}" font-family="sans-serif" font-size="{font:g}" text-anchor="middle" fill="#30312e"{text_transform}>{escape(dimension["label"])}</text>')
    out.append('</svg>')
    return ''.join(out)
