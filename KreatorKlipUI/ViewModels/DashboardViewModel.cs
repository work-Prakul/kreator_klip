using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using System.Collections.ObjectModel;
using System.Threading.Tasks;

namespace KreatorKlipUI.ViewModels
{
    public partial class DashboardViewModel : ObservableObject
    {
        [ObservableProperty]
        private int _globalProgress = 0;

        public ObservableCollection<string> LogOutput { get; } = new ObservableCollection<string>();
        
        // This is a mockup for VOD Queue
        public ObservableCollection<string> PendingVods { get; } = new ObservableCollection<string>();

        public DashboardViewModel()
        {
            PendingVods.Add("valorant_stream_2026_04_02.mp4");
        }

        [RelayCommand]
        public async Task StartProcessingAsync()
        {
            LogOutput.Clear();
            GlobalProgress = 0;
            // Bridge call would go here:
            // await _pythonBridge.RunKreatorKlipAsync("file.mp4", "valorant");
        }
        
        public void AppendLog(string message)
        {
            LogOutput.Add(message);
        }
        
        public void UpdateProgress(int progress)
        {
            GlobalProgress = progress;
        }
    }
}
