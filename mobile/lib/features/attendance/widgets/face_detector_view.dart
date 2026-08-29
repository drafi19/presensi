import 'dart:async';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import '../../../core/theme.dart';

class FaceDetectorView extends StatefulWidget {
  final Future<void> Function(List<XFile> frames) onFramesCaptured;
  final VoidCallback onCameraFeedReady;
  final int framesToCapture;
  final Duration captureInterval;

  const FaceDetectorView({
    super.key,
    required this.onFramesCaptured,
    required this.onCameraFeedReady,
    this.framesToCapture = 5,
    this.captureInterval = const Duration(milliseconds: 400),
  });

  @override
  State<FaceDetectorView> createState() => _FaceDetectorViewState();
}

class _FaceDetectorViewState extends State<FaceDetectorView> {
  static List<CameraDescription> _cameras = [];
  CameraController? _controller;
  int _cameraIndex = -1;
  bool _isCapturing = false;
  bool _isInitDone = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  void _initialize() async {
    try {
      if (_cameras.isEmpty) {
        _cameras = await availableCameras();
      }
      
      if (_cameras.isEmpty) {
        _errorMessage = 'Tidak ada kamera yang ditemukan.';
        return;
      }
      
      // Find front camera
      for (var i = 0; i < _cameras.length; i++) {
        if (_cameras[i].lensDirection == CameraLensDirection.front) {
          _cameraIndex = i;
          break;
        }
      }
      
      // Fallback to first camera if front is not available (e.g. on web sometimes)
      if (_cameraIndex == -1 && _cameras.isNotEmpty) {
        _cameraIndex = 0;
      }

      if (_cameraIndex != -1) {
        await _startLiveFeed();
      } else {
        _errorMessage = 'Kamera gagal dipilih.';
      }
    } catch (e) {
      debugPrint('Error initializing camera: $e');
      _errorMessage = 'Gagal mengakses kamera: $e';
    } finally {
      if (mounted) {
        setState(() {
          _isInitDone = true;
        });
      }
    }
  }

  @override
  void dispose() {
    _stopLiveFeed();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_isInitDone) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Menyiapkan kamera...', style: TextStyle(color: Colors.white)),
          ],
        ),
      );
    }
    
    if (_errorMessage != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Text(
            _errorMessage!,
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.red, fontSize: 16),
          ),
        ),
      );
    }

    if (_controller == null || _controller?.value.isInitialized == false) {
      return const Center(child: Text('Kamera tidak siap.', style: TextStyle(color: Colors.white)));
    }

    final size = MediaQuery.of(context).size;
    var scale = size.aspectRatio * _controller!.value.aspectRatio;
    if (scale < 1) scale = 1 / scale;

    return Container(
      color: Colors.black,
      child: Stack(
        fit: StackFit.expand,
        children: <Widget>[
          Transform.scale(
            scale: scale,
            child: Center(
              child: CameraPreview(_controller!),
            ),
          ),
          // Face overlay guides
          Center(
            child: Container(
              width: 250,
              height: 350,
              decoration: BoxDecoration(
                border: Border.all(
                  color: _isCapturing ? AppTheme.secondaryColor : AppTheme.primaryColor, 
                  width: 3
                ),
                borderRadius: BorderRadius.circular(150),
              ),
            ),
          ),
          Positioned(
            bottom: 120,
            left: 0,
            right: 0,
            child: Center(
              child: ElevatedButton.icon(
                onPressed: _isCapturing ? null : _captureFrames,
                icon: const Icon(Icons.camera_alt),
                label: Text(_isCapturing ? 'Verifying...' : 'Verify My Face'),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                  backgroundColor: AppTheme.primaryColor,
                  foregroundColor: Colors.white,
                ),
              ),
            ),
          ),
          const Positioned(
            bottom: 40,
            left: 0,
            right: 0,
            child: Text(
              'Align your face within the frame and press verify',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.bold,
                shadows: [
                  Shadow(color: Colors.black, blurRadius: 4),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _startLiveFeed() async {
    final camera = _cameras[_cameraIndex];
    _controller = CameraController(
      camera,
      ResolutionPreset.medium, // Medium is usually enough for face detection and saves bandwidth
      enableAudio: false,
    );
    await _controller?.initialize();
    if (mounted) {
      widget.onCameraFeedReady();
    }
  }

  Future _stopLiveFeed() async {
    await _controller?.dispose();
    _controller = null;
  }

  Future<void> _captureFrames() async {
    if (_isCapturing || _controller == null || !_controller!.value.isInitialized) return;
    
    setState(() {
      _isCapturing = true;
    });

    List<XFile> capturedFrames = [];
    
    try {
      for (int i = 0; i < widget.framesToCapture; i++) {
        final XFile file = await _controller!.takePicture();
        capturedFrames.add(file);
        
        if (i < widget.framesToCapture - 1) {
          await Future.delayed(widget.captureInterval);
        }
      }
      
      // Pass the frames back to parent
      await widget.onFramesCaptured(capturedFrames);
    } catch (e) {
      debugPrint("Error capturing frames: $e");
    } finally {
      if (mounted) {
        setState(() {
          _isCapturing = false;
        });
      }
    }
  }
}
