using System;
using System.Diagnostics;
using System.Globalization;
using System.Threading;
using UnityEngine;

public class PythonRunner : MonoBehaviour
{
    public string pythonExe = "py";
    public CameraControl cameraControl;
    public Shooter shooter;

    private Process pythonProcess;
    private Thread outputThread;
    private Thread errorThread;

    private volatile float latestVx = 0f;
    private volatile float latestVy = 0f;
    private volatile bool hasNewVector = false;

    private volatile float latestShotStrength = 0f;
    private volatile bool shotTriggered = false;

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

        if (shotTriggered && shooter != null)
        {
            shooter.Shoot(latestShotStrength);
            shotTriggered = false;
        }
    }

    void OnApplicationQuit()
    {
        StopPython();
    }

    private void StartPython()
    {
        pythonProcess = new Process();
        pythonProcess.StartInfo.FileName = pythonExe;
        
        pythonProcess.StartInfo.WorkingDirectory = Application.dataPath;
        pythonProcess.StartInfo.Arguments = "hand_control.py";

        pythonProcess.StartInfo.UseShellExecute = false;
        pythonProcess.StartInfo.RedirectStandardOutput = true;
        pythonProcess.StartInfo.RedirectStandardError = true;
        pythonProcess.StartInfo.CreateNoWindow = true;

        pythonProcess.Start();

        UnityEngine.Debug.Log("PYTHON STARTED in: " + pythonProcess.StartInfo.WorkingDirectory);

        outputThread = new Thread(ReadOutput);
        outputThread.IsBackground = true;
        outputThread.Start();

        errorThread = new Thread(ReadError);
        errorThread.IsBackground = true;
        errorThread.Start();
    }

    private void ReadOutput()
    {
        var ci = CultureInfo.InvariantCulture;

        while (pythonProcess != null && !pythonProcess.HasExited)
        {
            string line = pythonProcess.StandardOutput.ReadLine();
            if (string.IsNullOrEmpty(line))
                continue;

            UnityEngine.Debug.Log("PY OUT: " + line);

            // ---------- SHOT ----------
            if (line.StartsWith("SHOT"))
            {
                string[] parts = line.Split(' ');
                if (parts.Length >= 2 &&
                    float.TryParse(parts[1], NumberStyles.Float, ci, out float s))
                {
                    latestShotStrength = s;
                    shotTriggered = true;
                }
                continue;
            }

            // ---------- VECTORS ----------
            string[] xy = line.Split(' ');
            if (xy.Length == 2 &&
                float.TryParse(xy[0], NumberStyles.Float, ci, out float vx) &&
                float.TryParse(xy[1], NumberStyles.Float, ci, out float vy))
            {
                latestVx = vx;
                latestVy = vy;
                hasNewVector = true;
            }
        }
    }

    private void ReadError()
    {
        while (pythonProcess != null && !pythonProcess.HasExited)
        {
            string err = pythonProcess.StandardError.ReadLine();
            if (!string.IsNullOrEmpty(err))
                UnityEngine.Debug.LogError("PY ERR: " + err);
        }
    }

    private void StopPython()
    {
        try
        {
            if (pythonProcess != null && !pythonProcess.HasExited)
                pythonProcess.Kill();
        }
        catch { }

        pythonProcess = null;
    }
}
