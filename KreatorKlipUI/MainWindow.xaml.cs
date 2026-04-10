using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using System;

namespace KreatorKlipUI
{
    public partial class MainWindow : Window
    {
        public MainWindow()
        {
            this.InitializeComponent();
            ExtendsContentIntoTitleBar = true;
            SetTitleBar(null); // Use custom drag region if needed, or default full.
            NavView.SelectedItem = NavView.MenuItems[0];
            ContentFrame.Navigate(typeof(Views.DashboardView));
        }

        private void NavView_SelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
        {
            if (args.IsSettingsSelected)
            {
                // ContentFrame.Navigate(typeof(Views.SettingsView));
            }
            else
            {
                var selectedItem = (NavigationViewItem)args.SelectedItem;
                string tag = selectedItem.Tag.ToString();
                
                if (tag == "DashboardView") ContentFrame.Navigate(typeof(Views.DashboardView));
                else if (tag == "GalleryView") ContentFrame.Navigate(typeof(Views.GalleryView));
            }
        }
    }
}
