import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../widgets/face_detector_view.dart';
import '../../auth/providers/auth_provider.dart';
import '../../../core/theme.dart';
import '../../../core/api_service.dart';

class AttendanceScreen extends StatefulWidget {
  const AttendanceScreen({super.key});

  @override
  State<AttendanceScreen> createState() => _AttendanceScreenState();
}

class _AttendanceScreenState extends State<AttendanceScreen> {
  String? _statusMessage;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AI Recognition Attendance')),
      body: Stack(
        children: [
          FaceDetectorView(
            onFramesCaptured: _processFrames,
            onCameraFeedReady: () {
              setState(() {
                _statusMessage = 'Ready. Please align your face and verify.';
              });
            },
          ),
          if (_statusMessage != null)
            Positioned(
              top: 16,
              left: 16,
              right: 16,
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
                decoration: BoxDecoration(
                  color: Colors.black54,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  _statusMessage!,
                  style: const TextStyle(color: Colors.white, fontSize: 16),
                  textAlign: TextAlign.center,
                ),
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _processFrames(List<XFile> frames) async {
    setState(() {
      _statusMessage = 'Sending ${frames.length} frames to server...';
    });

    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    // Kita hapus pengiriman userId agar API melakukan pencarian 1:N (mencari siapa orang ini di database)
    // sebelumnya mengirim 'Alex Developer' yang membuat API bingung.
    
    try {
      final response = await ApiService.verifyFace(frames, null);
      
      if (!mounted) return;
      
      final String status = response['status'] ?? 'unknown';
      final double confidence = (response['confidence'] ?? 0.0).toDouble();
      
      setState(() {
        _statusMessage = 'Verification complete.';
      });

      _showResultDialog(status, confidence);
    } catch (e) {
      if (!mounted) return;
      
      setState(() {
        _statusMessage = 'Error occurred.';
      });
      
      _showErrorDialog(e.toString());
    }
  }

  void _showResultDialog(String status, double confidence) {
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    
    final bool isSuccess = status == 'match';
    
    String title = 'Recognition Failed';
    String message = 'We couldn\'t verify your identity. Please try again.';
    IconData icon = Icons.error;
    Color color = AppTheme.errorColor;
    
    if (isSuccess) {
      title = 'Attendance Logged';
      message = 'Status: Checked In';
      icon = Icons.check_circle;
      color = AppTheme.secondaryColor;
    } else if (status == 'spoof') {
      message = 'Spoofing detected. Please use a real face.';
    } else if (status == 'no_face') {
      message = 'No face detected in the frames.';
    } else if (status == 'low_quality') {
      message = 'Image quality is too low. Please move to a brighter area.';
    }
    
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) {
        return AlertDialog(
          backgroundColor: AppTheme.surfaceColor,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          title: Icon(
            icon,
            color: color,
            size: 64,
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                title,
                style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              if (isSuccess) ...[
                Text('Employee: ${authProvider.employeeName}'),
                Text('Time: ${DateTime.now().toString().split('.')[0]}'),
                Text('Confidence: ${(confidence * 100).toStringAsFixed(1)}%'),
                const SizedBox(height: 8),
                Text(message, style: const TextStyle(fontWeight: FontWeight.bold)),
              ] else ...[
                Text(message, textAlign: TextAlign.center),
                if (confidence > 0) Text('Score: ${(confidence * 100).toStringAsFixed(1)}%'),
              ]
            ],
          ),
          actions: [
            if (!isSuccess)
              TextButton(
                onPressed: () {
                  Navigator.of(context).pop();
                  setState(() {
                    _statusMessage = 'Ready. Please align your face and verify.';
                  });
                },
                child: const Text('Retry'),
              ),
            TextButton(
              onPressed: () {
                Navigator.of(context).pop(); // Close dialog
                context.go('/home'); // Go back home
              },
              child: Text(isSuccess ? 'Done' : 'Cancel'),
            ),
          ],
        );
      },
    );
  }

  void _showErrorDialog(String error) {
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Network Error'),
          content: Text(error),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('OK'),
            ),
          ],
        );
      }
    );
  }
}
