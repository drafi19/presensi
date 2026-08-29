import 'dart:convert';
import 'package:camera/camera.dart';
import 'package:http/http.dart' as http;

class ApiService {
  // PENTING: Sesuaikan URL ini!
  // Jika pakai Emulator Android: gunakan 'http://10.0.2.2:8000/api'
  // Jika pakai HP asli (kabel/Wi-Fi): gunakan IP laptop Anda (misal: 'http://192.168.1.15:8000/api')
  // Jika pakai iOS Simulator / Web: gunakan 'http://localhost:8000/api'
  static const String baseUrl = 'http://192.168.18.51:8000/api'; // Menggunakan IP dari Swagger Docs Anda

  static Future<Map<String, dynamic>> verifyFace(List<XFile> frames, String? userId) async {
    final uri = Uri.parse('$baseUrl/verify');
    final request = http.MultipartRequest('POST', uri);

    if (userId != null && userId.isNotEmpty) {
      request.fields['user_id'] = userId;
    }

    // Add all frames to the multipart request
    for (var i = 0; i < frames.length; i++) {
      final file = frames[i];
      final bytes = await file.readAsBytes();
      request.files.add(
        http.MultipartFile.fromBytes(
          'files', // Diubah menjadi 'files' sesuai permintaan error API
          bytes,
          filename: 'frame_$i.jpg',
        ),
      );
    }

    // Add API key if needed as specified in DESAIN.md
    request.headers['X-API-Key'] = 'dev-key-change-me';

    try {
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode >= 200 && response.statusCode < 300) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Server error: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      throw Exception('Failed to communicate with API server: $e');
    }
  }
}
