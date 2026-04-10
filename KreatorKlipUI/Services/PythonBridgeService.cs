using System;
using System.Diagnostics;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Microsoft.UI.Dispatching; // WinUI 3 Dispatcher

namespace KreatorKlipUI.Services
{
    public class PythonBridgeService
    {
        private DispatcherQueue _dispatcherQueue;
        
        public Action<string> OnLogReceived { get; set; }
        public Action<int> OnProgressUpdated { get; set; }

        public PythonBridgeService(DispatcherQueue dispatcherQueue)
        {
            _dispatcherQueue = dispatcherQueue;
        }

        public async Task RunKreatorKlipAsync(string videoPath, string targetGame)
        {
            await Task.Run(() =>
            {
                var processInfo = new ProcessStartInfo
                {
                    FileName = "python",
                    Arguments = $"main.py \"{videoPath}\" --game {targetGame}",
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                    WorkingDirectory = Environment.CurrentDirectory
                };

                using (var process = new Process { StartInfo = processInfo })
                {
                    process.OutputDataReceived += Process_OutputDataReceived;
                    process.ErrorDataReceived += Process_ErrorDataReceived;

                    process.Start();
                    process.BeginOutputReadLine();
                    process.BeginErrorReadLine();
                    process.WaitForExit();
                }
            });
        }

        private void Process_OutputDataReceived(object sender, DataReceivedEventArgs e)
        {
            if (!string.IsNullOrEmpty(e.Data))
            {
                // Parse PROGRESS: 45%
                var progressMatch = Regex.Match(e.Data, @"PROGRESS:\s*(\d+)%");
                
                _dispatcherQueue.TryEnqueue(() =>
                {
                    if (progressMatch.Success && int.TryParse(progressMatch.Groups[1].Value, out int progress))
                    {
                        OnProgressUpdated?.Invoke(progress);
                    }
                    OnLogReceived?.Invoke(e.Data);
                });
            }
        }

        private void Process_ErrorDataReceived(object sender, DataReceivedEventArgs e)
        {
            if (!string.IsNullOrEmpty(e.Data))
            {
                _dispatcherQueue.TryEnqueue(() =>
                {
                    OnLogReceived?.Invoke($"[ERROR] {e.Data}");
                });
            }
        }
    }
}
