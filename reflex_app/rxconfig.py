import reflex as rx

config = rx.Config(
    app_name="visualfil_reflex",
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(accent_color="indigo", radius="medium")
        ),
        rx.plugins.SitemapPlugin(),
    ],
)
