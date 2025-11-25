using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class CameraControl : MonoBehaviour
{
    public Transform cam;
    public float sensitivity = 200f;

    float pitch = 0f;

    public void ApplyVector(float vx, float vy)
    {
        // yaw (left/right)
        transform.Rotate(Vector3.up * vx * sensitivity);

        // pitch (up/down)
        pitch += vy * sensitivity;
        pitch = Mathf.Clamp(pitch, -80f, 80f);

        cam.localRotation = Quaternion.Euler(pitch, 0f, 0f);
    }
}

