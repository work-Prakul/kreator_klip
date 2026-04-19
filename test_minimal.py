import flet as ft

def main(page: ft.Page):
    try:
        page.title = "Test"
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    ft.run(main)
