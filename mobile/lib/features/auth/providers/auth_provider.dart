import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AuthProvider with ChangeNotifier {
  bool _isAuthenticated = false;
  String? _employeeId;
  String? _employeeName;
  String? _jobTitle;

  bool get isAuthenticated => _isAuthenticated;
  String? get employeeId => _employeeId;
  String? get employeeName => _employeeName;
  String? get jobTitle => _jobTitle;

  Future<void> checkAuthStatus() async {
    final prefs = await SharedPreferences.getInstance();
    _isAuthenticated = prefs.getBool('is_authenticated') ?? false;
    if (_isAuthenticated) {
      _employeeId = prefs.getString('emp_id');
      _employeeName = prefs.getString('emp_name');
      _jobTitle = prefs.getString('job_title');
    }
    notifyListeners();
  }

  Future<bool> login(String id, String password) async {
    // Mock login logic
    await Future.delayed(const Duration(seconds: 1)); // Simulate network request
    
    // In a real app, you would validate against a backend.
    if (id.isNotEmpty && password.isNotEmpty) {
      _isAuthenticated = true;
      _employeeId = id;
      _employeeName = "Alex Developer"; // Mock name
      _jobTitle = "Senior Software Engineer"; // Mock job title
      
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool('is_authenticated', true);
      await prefs.setString('emp_id', _employeeId!);
      await prefs.setString('emp_name', _employeeName!);
      await prefs.setString('job_title', _jobTitle!);
      
      notifyListeners();
      return true;
    }
    return false;
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    
    _isAuthenticated = false;
    _employeeId = null;
    _employeeName = null;
    _jobTitle = null;
    
    notifyListeners();
  }
}
