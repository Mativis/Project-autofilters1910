import reflex as rx

config = rx.Config(
    app_name="visualfil_reflex",
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                appearance="light",
                accent_color="blue",
                gray_color="slate",
                radius="large",
            )
        ),
        rx.plugins.SitemapPlugin(),
    ],
)
