// Checks the saved OEM template using the native libfprint device driver.
#include <fprint.h>
#include "fpi-print.h"
#include <stdio.h>
#include <string.h>

static void finger_status(FpDevice *device, GParamSpec *spec, gpointer data)
{
    (void)spec; (void)data;
    if (fp_device_get_finger_status(device) & FP_FINGER_STATUS_NEEDED) {
        puts("READY"); fflush(stdout);
    }
}

int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    g_autoptr(FpContext) context = fp_context_new();
    GPtrArray *devices = fp_context_get_devices(context);
    if (devices->len != 1) {
        fprintf(stderr, "Expected one ELAN OEM reader; found %u\n", devices->len);
        return 2;
    }
    FpDevice *device = g_ptr_array_index(devices, 0);
    g_autoptr(GError) error = NULL;
    if (!fp_device_open_sync(device, NULL, &error)) {
        fprintf(stderr, "%s\n", error->message);
        return 2;
    }
    int status = 0;
    if (strcmp(argv[1], "--open") != 0) {
        g_autofree gchar *data = NULL;
        gsize size = 0;
        if (!g_file_get_contents(argv[1], &data, &size, &error) || !size || size > 1024 * 1024) {
            fprintf(stderr, "Cannot read the OEM template\n");
            status = 2;
        } else {
            g_autoptr(FpPrint) print = g_object_ref_sink(fp_print_new(device));
            GVariant *bytes = g_variant_new_fixed_array(G_VARIANT_TYPE_BYTE, data, size, 1);
            g_object_set(print, "fpi-type", FPI_PRINT_RAW, "fpi-data", g_variant_new("(@ay)", bytes), NULL);
            g_signal_connect(device,"notify::finger-status",G_CALLBACK(finger_status),NULL);
            gboolean matched = FALSE;
            if (!fp_device_verify_sync(device, print, NULL, NULL, NULL, &matched, NULL, &error)) {
                fprintf(stderr, "%s\n", error->message);
                status = 2;
            } else {
                puts(matched ? "MATCH" : "NO MATCH");
                status = matched ? 0 : 1;
            }
        }
    }
    if (!fp_device_close_sync(device, NULL, NULL)) status = 2;
    return status;
}
