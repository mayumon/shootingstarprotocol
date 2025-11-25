using System.Diagnostics;
using System.Threading;
using System.Globalization;
using UnityEngine;

public class PythonRunner : MonoBehaviour
{
    public string pythonExe = "py";
    public string scriptPath = "hand_control.py";
    public CameraControl cameraControl;

    private Process pythonProcess;
    private Thread outputThread;
    private Thread errorThread;

    private volatile float latestVx = 0f;
    private volatile float latestVy = 0f;
    private volatile bool hasNewVector = false;

    void Start()
    {
        StartPython();
    }

    void Update()
    {
        if (hasNewVector && cameraControl != null)
        {
            cameraControl.ApplyVector(latestVx, latestVy);
            hasNewVector = false;
        }
    }

    void OnApplicationQuit()
    {
        StopPython();
    }

    void StartPython()
    {
        pythonProcess = new Process();
        pythonProcess.StartInfo.FileName = pythonExe;

        string fullPath = System.IO.Path.Combine(Application.dataPath, scriptPath);
        pythonProcess.StartInfo.Arguments = "\"" + fullPath + "\"";

        pythonProcess.StartInfo.CreateNoWindow = true;
        pythonProcess.StartInfo.UseShellExecute = false;
        pythonProcess.StartInfo.RedirectStandardOutput = true;
        pythonProcess.StartInfo.RedirectStandardError = true;

        pythonProcess.Start();

        UnityEngine.Debug.Log("PYTHON STARTED: " + fullPath);

        outputThread = new Thread(ReadOutput) { IsBackground = true };
        outputThread.Start();

        errorThread = new Thread(ReadError) { IsBackground = true };
        errorThread.Start();
    }

    void ReadOutput()
    {
        var ci = CultureInfo.InvariantCulture;

        while (!pythonProcess.HasExited)
        {
            string line = pythonProcess.StandardOutput.ReadLine();
            if (string.IsNullOrEmpty(line))
                continue;

            UnityEngine.Debug.Log("PY: " + line);

            string[] parts = line.Split(' ');
            if (parts.Length >= 2 &&
                float.TryParse(parts[0], NumberStyles.Float, ci, out float vx) &&
                float.TryParse(parts[1], NumberStyles.Float, ci, out float vy))
            {
                latestVx = vx;
                latestVy = vy;
                hasNewVector = true;
            }
        }
    }

    void ReadError()
    {
        while (!pythonProcess.HasExited)
        {
            string line = pythonProcess.StandardError.ReadLine();
            if (string.IsNullOrEmpty(line))
                continue;

            UnityEngine.Debug.LogError("PY ERR: " + line);
        }
    }

    void StopPython()
    {
        try
        {
            if (pythonProcess != null && !pythonProcess.HasExited)
            {
                pythonProcess.Kill();
            }
        }
        catch { }
    }
}
