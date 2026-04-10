using Microsoft.UI.Xaml.Controls;
using KreatorKlipUI.ViewModels;

namespace KreatorKlipUI.Views
{
    public sealed partial class DashboardView : Page
    {
        public DashboardViewModel ViewModel { get; } = new DashboardViewModel();
        
        public DashboardView()
        {
            this.InitializeComponent();
        }
    }
}
