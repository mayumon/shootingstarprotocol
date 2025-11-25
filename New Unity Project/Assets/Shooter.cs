using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Shooter : MonoBehaviour
{
    public GameObject projectilePrefab;
    public Transform firePoint;
    public float maxForce = 20f;

    public void Shoot(float strength)
    {
        strength = Mathf.Clamp01(strength);

        Debug.Log($"[Shooter] Shoot() called, strength = {strength}");

        if (projectilePrefab == null)
        {
            Debug.LogWarning("[Shooter] projectilePrefab not assigned");
            return;
        }
        if (firePoint == null)
        {
            Debug.LogWarning("[Shooter] firePoint not assigned");
            return;
        }

        GameObject proj = Instantiate(projectilePrefab, firePoint.position, firePoint.rotation);
        Debug.Log($"[Shooter] Spawned projectile: {proj.name} at {firePoint.position}");

        Rigidbody rb = proj.GetComponent<Rigidbody>();
        if (rb == null)
        {
            Debug.LogWarning("[Shooter] projectilePrefab missing Rigidbody");
            return;
        }

        rb.AddForce(firePoint.forward * strength * maxForce, ForceMode.VelocityChange);
        Debug.Log($"[Shooter] Added force: {firePoint.forward * strength * maxForce}");
    }
}
