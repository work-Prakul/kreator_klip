import flet as ft
from dataclasses import dataclass

@dataclass
class Session:
    pass

sess = Session()
page = ft.Page(sess)
print(f'SUCCESS: Page created with Session')
print(f'Page title: {page.title}')
