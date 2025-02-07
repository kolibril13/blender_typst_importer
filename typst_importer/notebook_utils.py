from IPython.display import display, HTML


def display_svg(svg_content, width='100px'):
    html_content = (
        "<style>"
        ".svg-container svg { max-width: 100%; height: auto; display: block; }"
        "</style>"
    )
    html_content += f"<div class='svg-container' style='width:{width};'>{svg_content}</div>"
    display(HTML(html_content))
