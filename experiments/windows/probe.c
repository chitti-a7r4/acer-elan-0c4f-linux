// Offline WinBio engine probe for the ELAN 04f3:0c4f reader.
#include <windows.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <io.h>
#ifndef ARGUMENT_PRESENT
#define ARGUMENT_PRESENT(value) ((value) != NULL)
#endif
#include <winbio_adapter.h>

enum { WIDTH = 80, HEIGHT = 80 };

static HRESULT WINAPI sensor_control(PWINBIO_PIPELINE pipeline, ULONG code,
    PUCHAR input, SIZE_T input_size, PUCHAR output, SIZE_T capacity,
    PSIZE_T used, PULONG status)
{
    (void)pipeline;
    printf("Sensor control 0x%08lx, %zu output bytes\n", code, capacity);
    *used = 0;
    *status = ERROR_NOT_SUPPORTED;
    // SCUCMD_RECEIVE_ENGINE_INFO in this Acer WbfUsbDriver copies the
    // engine's own 268-byte message into the equally sized reply.
    if (code == 0x4421c0 && input && output && input_size == 268 && capacity == 268) {
        memmove(output, input, input_size);
        *used = input_size;
        *status = ERROR_SUCCESS;
        return S_OK;
    }
    // Dimension query documented by the elan_oem reference implementation.
    if (code != 0x442080 || capacity != 2 * sizeof(ULONG) || !output)
        return E_NOTIMPL;
    const ULONG geometry[] = {WIDTH, HEIGHT};
    memcpy(output, geometry, sizeof geometry);
    *used = sizeof geometry;
    *status = ERROR_SUCCESS;
    return S_OK;
}

static HRESULT log_result(const char *name, HRESULT result)
{
    printf("%s: 0x%08lx\n", name, (ULONG)result);
    return result;
}

// In-memory WinBio representation of one uncompressed, uniformly gray test image.
struct sample {
    WINBIO_BIR bir;
    WINBIO_BIR_HEADER header;
    WINBIO_BDB_ANSI_381_HEADER image;
    WINBIO_BDB_ANSI_381_RECORD view;
    BYTE pixels[HEIGHT * WIDTH];
};

static HRESULT test_sample(WINBIO_PIPELINE *pipeline, BOOL live)
{
    struct sample sample = {0};
    const size_t image_end = offsetof(struct sample, pixels) + sizeof sample.pixels;
    sample.bir.HeaderBlock.Offset = offsetof(struct sample, header);
    sample.bir.HeaderBlock.Size = sizeof sample.header;
    sample.bir.StandardDataBlock.Offset = offsetof(struct sample, image);
    sample.bir.StandardDataBlock.Size = image_end - offsetof(struct sample, image);
    sample.header.ValidFields = WINBIO_BIR_FIELD_CBEFF_HEADER_VERSION |
        WINBIO_BIR_FIELD_PATRON_HEADER_VERSION | WINBIO_BIR_FIELD_BIOMETRIC_TYPE |
        WINBIO_BIR_FIELD_BIOMETRIC_SUBTYPE | WINBIO_BIR_FIELD_BIOMETRIC_PURPOSE;
    sample.header.HeaderVersion = WINBIO_CBEFF_HEADER_VERSION;
    sample.header.PatronHeaderVersion = WINBIO_PATRON_HEADER_VERSION;
    sample.header.Type = WINBIO_TYPE_FINGERPRINT;
    sample.header.Subtype = WINBIO_ANSI_381_POS_RH_INDEX_FINGER;
    sample.header.Purpose = WINBIO_PURPOSE_ENROLL;
    sample.header.DataFlags = WINBIO_DATA_FLAG_RAW | WINBIO_DATA_FLAG_OPTION_MASK_PRESENT;
    sample.header.BiometricDataFormat.Owner = WINBIO_ANSI_381_FORMAT_OWNER;
    sample.header.BiometricDataFormat.Type = WINBIO_ANSI_381_FORMAT_TYPE;
    sample.image.RecordLength = sample.bir.StandardDataBlock.Size;
    sample.image.FormatIdentifier = 0x46495200;
    sample.image.VersionNumber = 0x30313000;
    sample.image.ScaleUnits = WINBIO_ANSI_381_PIXELS_PER_INCH;
    // Match the legacy ELAN prototype's convention for these synthetic fields.
    sample.image.HorizontalScanResolution = sample.image.HorizontalImageResolution = WIDTH;
    sample.image.VerticalScanResolution = sample.image.VerticalImageResolution = HEIGHT;
    sample.image.ElementCount = 1;
    sample.image.PixelDepth = 8;
    sample.view.BlockLength = image_end - offsetof(struct sample, view);
    sample.view.HorizontalLineLength = WIDTH;
    sample.view.VerticalLineLength = HEIGHT;
    sample.view.Position = sample.header.Subtype;
    sample.view.CountOfViews = sample.view.ViewNumber = 1;
    sample.view.ImageQuality = 254;
    if (live) {
        _setmode(_fileno(stdin), _O_BINARY);
        if (fread(sample.pixels, 1, sizeof sample.pixels, stdin) != sizeof sample.pixels || fgetc(stdin) != EOF)
            return E_INVALIDARG;
    } else {
        memset(sample.pixels, 128, sizeof sample.pixels);
    }
    WINBIO_REJECT_DETAIL reject = 0;
    HRESULT hr = log_result(live ? "Accept captured sample" : "Accept blank sample", pipeline->EngineInterface->AcceptSampleData(
        pipeline, &sample.bir, image_end, WINBIO_PURPOSE_ENROLL, &reject));
    printf("Sample reject detail: %lu\n", reject);
    if (hr == S_OK) {
        reject = 0;
        hr = log_result("Update test enrollment", pipeline->EngineInterface->UpdateEnrollment(pipeline, &reject));
        printf("Enrollment reject detail: %lu\n", reject);
    }
    return hr;
}

int main(int argc, char **argv)
{
    BOOL live = argc == 2 && strcmp(argv[1], "--frame-stdin") == 0;
    if (argc != 1 && !live) return 2;
    setvbuf(stdout, NULL, _IONBF, 0);
    HMODULE dll = LoadLibraryW(L".\\EngineAdapter.dll");
    if (!dll) {
        fprintf(stderr, "LoadLibrary failed: %lu\n", GetLastError());
        return 1;
    }
    PWINBIO_QUERY_ENGINE_INTERFACE_FN query =
        (PWINBIO_QUERY_ENGINE_INTERFACE_FN)GetProcAddress(dll, WINBIO_QUERY_ENGINE_INTERFACE_FN_NAME);
    PWINBIO_ENGINE_INTERFACE engine = NULL;
    if (!query || FAILED(log_result("Query interface", query(&engine))) || !engine)
        return 1;
    printf("Engine interface %u.%u, type %lu, size %zu\n",
           engine->Version.MajorVersion, engine->Version.MinorVersion, engine->Type, engine->Size);
    if (engine->Type != WINBIO_ADAPTER_TYPE_ENGINE ||
        engine->Size < offsetof(WINBIO_ENGINE_INTERFACE, DiscardEnrollment) + sizeof(engine->DiscardEnrollment))
        return 1;
    WINBIO_SENSOR_INTERFACE sensor = {0};
    sensor.Version.MajorVersion = 1;
    sensor.Type = WINBIO_ADAPTER_TYPE_SENSOR;
    sensor.Size = sizeof sensor;
    sensor.ControlUnit = sensor_control;
    WINBIO_STORAGE_INTERFACE storage = {0};
    storage.Version.MajorVersion = 1;
    storage.Type = WINBIO_ADAPTER_TYPE_STORAGE;
    storage.Size = sizeof storage;
    WINBIO_PIPELINE pipeline = {0};
    pipeline.EngineHandle = INVALID_HANDLE_VALUE;
    pipeline.SensorInterface = &sensor;
    pipeline.StorageInterface = &storage;
    pipeline.EngineInterface = engine;
    HRESULT result = log_result("Attach", engine->Attach(&pipeline));
    if (FAILED(result)) return 1;
    WINBIO_REGISTERED_FORMAT format = {0};
    GUID vendor = {0};
    result = log_result("Preferred format",engine->QueryPreferredFormat(&pipeline,&format,&vendor));
    if (SUCCEEDED(result))
        printf("Format owner 0x%04x type 0x%04x\n",format.Owner,format.Type);
    SIZE_T hint = 0;
    if (SUCCEEDED(log_result("Sample hint",engine->QuerySampleHint(&pipeline,&hint))))
        printf("Sample hint: %zu\n",hint);
    result = log_result("Create enrollment",engine->CreateEnrollment(&pipeline));
    if (SUCCEEDED(result)) {
        HRESULT sample_result = test_sample(&pipeline, live);
        // A blank image is a negative control. Its rejection does not validate
        // the input format for genuine finger samples.
        result = live ? sample_result : (sample_result == WINBIO_E_BAD_CAPTURE ? S_OK : E_FAIL);
        log_result("Discard test enrollment",engine->DiscardEnrollment(&pipeline));
    }
    log_result("Detach",engine->Detach(&pipeline));
    FreeLibrary(dll);
    return FAILED(result);
}
