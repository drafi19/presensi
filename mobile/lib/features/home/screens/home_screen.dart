import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../../auth/providers/auth_provider.dart';
import '../../../core/theme.dart';
import 'dart:async';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);

    return Scaffold(
      backgroundColor: AppTheme.scaffoldLight,
      body: SingleChildScrollView(
        child: Column(
          children: [
            _buildTopSection(context, authProvider),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24.0),
              child: Column(
                children: [
                  const SizedBox(height: 24),
                  _buildAttendanceHeader(),
                  const SizedBox(height: 16),
                  const _AttendanceStatsCard(),
                  const SizedBox(height: 24),
                  _buildMainMenu(context),
                  const SizedBox(height: 120), // Extra padding for the floating navigation bar
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTopSection(BuildContext context, AuthProvider authProvider) {
    return Stack(
      clipBehavior: Clip.none,
      children: [
        // Black background behind everything at the top
        Container(
          height: 260,
          width: double.infinity,
          decoration: const BoxDecoration(
            color: AppTheme.cardDark,
            borderRadius: BorderRadius.only(
              bottomLeft: Radius.circular(24),
              bottomRight: Radius.circular(24),
            ),
          ),
        ),
        SafeArea(
          bottom: false,
          child: Column(
            children: [
              // User Info Row with top red line
              Container(
                margin: const EdgeInsets.only(top: 16),
                decoration: const BoxDecoration(
                  border: Border(
                    top: BorderSide(color: Colors.deepOrange, width: 1.0),
                  ),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 24.0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        const CircleAvatar(
                          radius: 24,
                          backgroundColor: Color(0xFF2C3241), // dark bluish grey avatar background
                        ),
                        const SizedBox(width: 16),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              authProvider.employeeName ?? 'John Alex',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              authProvider.jobTitle ?? 'UI/UX Designer',
                              style: const TextStyle(
                                color: Colors.white70,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                    IconButton(
                      icon: const Icon(Icons.logout, color: Colors.redAccent),
                      onPressed: () async {
                        await authProvider.logout();
                        if (context.mounted) {
                          context.go('/login');
                        }
                      },
                    )
                  ],
                ),
              ),
              // Overlapping Working Time Card
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 24.0),
                child: _WorkingTimeCard(),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildAttendanceHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        RichText(
            text: const TextSpan(
                style: TextStyle(color: Colors.black, fontSize: 16, fontFamily: 'Inter'), // Assuming default font
                children: [
              TextSpan(text: 'Total Attendance', style: TextStyle(fontWeight: FontWeight.bold)),
              TextSpan(text: '(days)', style: TextStyle(color: Colors.blueGrey, fontSize: 12)),
            ])),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: AppTheme.cardDark,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Row(
            children: const [
              Text('August', style: TextStyle(color: Colors.white, fontSize: 14)),
              SizedBox(width: 4),
              Icon(Icons.keyboard_arrow_down, color: Colors.white, size: 16),
            ],
          ),
        )
      ],
    );
  }

  Widget _buildMainMenu(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 32, horizontal: 24),
      decoration: BoxDecoration(
        color: AppTheme.cardDark,
        borderRadius: BorderRadius.circular(32),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildMenuItem(context, 'Task', Icons.check_box_outlined, AppTheme.accentOrange, '/home/tasks'),
              _buildMenuItem(context, 'Office Event', Icons.calendar_today_outlined, AppTheme.iconBlueDark, '/home/events'),
            ],
          ),
          const SizedBox(height: 32),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildMenuItem(context, 'Office News', Icons.campaign_outlined, AppTheme.iconBlueDark, '/home/news'),
              _buildMenuItem(context, 'Attendance', Icons.access_time, AppTheme.iconBlueDark, null),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMenuItem(BuildContext context, String title, IconData icon, Color bgColor, String? route) {
    return GestureDetector(
      onTap: () {
        if (route != null) {
          context.go(route);
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Use the bottom navigation to access Attendance.')),
          );
        }
      },
      behavior: HitTestBehavior.opaque,
      child: Column(
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: bgColor,
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: Colors.white, size: 28),
          ),
          const SizedBox(height: 12),
          Text(
            title,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

class _AttendanceStatsCard extends StatelessWidget {
  const _AttendanceStatsCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 24),
      decoration: BoxDecoration(
        color: AppTheme.cardDark,
        borderRadius: BorderRadius.circular(32),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _buildStat('09', 'Present'),
          _buildStat('30', 'Late'),
          _buildStat('59', 'Absent'),
        ],
      ),
    );
  }

  Widget _buildStat(String count, String label) {
    return Column(
      children: [
        Text(
          count,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 28,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 12,
          ),
        ),
      ],
    );
  }
}

class _WorkingTimeCard extends StatefulWidget {
  const _WorkingTimeCard();

  @override
  State<_WorkingTimeCard> createState() => _WorkingTimeCardState();
}

class _WorkingTimeCardState extends State<_WorkingTimeCard> {
  late Stream<DateTime> _clockStream;

  @override
  void initState() {
    super.initState();
    _clockStream = Stream.periodic(const Duration(seconds: 1), (_) => DateTime.now());
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      clipBehavior: Clip.none,
      alignment: Alignment.bottomCenter,
      children: [
        Container(
          width: double.infinity,
          margin: const EdgeInsets.only(bottom: 24), // Space for floating button
          padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 24),
          decoration: BoxDecoration(
            color: const Color(0xFF333333), // Dark grey card
            borderRadius: BorderRadius.circular(24),
          ),
          child: Column(
            children: [
              const Text(
                'Working Time',
                style: TextStyle(color: Colors.white70, fontSize: 14, fontWeight: FontWeight.w500),
              ),
              const SizedBox(height: 12),
              StreamBuilder<DateTime>(
                  stream: _clockStream,
                  builder: (context, snapshot) {
                    final now = snapshot.data ?? DateTime.now();
                    int hour = now.hour;
                    String ampm = hour >= 12 ? 'PM' : 'AM';
                    hour = hour % 12;
                    if (hour == 0) hour = 12;
                    String h = hour.toString().padLeft(2, '0');
                    String m = now.minute.toString().padLeft(2, '0');
                    String s = now.second.toString().padLeft(2, '0');

                    return Container(
                      padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 12),
                      decoration: BoxDecoration(
                        color: AppTheme.clockPillGrey,
                        borderRadius: BorderRadius.circular(30),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            h,
                            style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.white),
                          ),
                          const Padding(
                            padding: EdgeInsets.symmetric(horizontal: 4),
                            child: Text(':', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.white54)),
                          ),
                          Text(
                            m,
                            style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.white),
                          ),
                          const Padding(
                            padding: EdgeInsets.symmetric(horizontal: 4),
                            child: Text(':', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.white54)),
                          ),
                          Text(
                            s,
                            style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.white),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            ampm,
                            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white70),
                          ),
                        ],
                      ),
                    );
                  }),
              const SizedBox(height: 24), // Space inside the card before the button overlaps
            ],
          ),
        ),
        Positioned(
          bottom: 4, // Overlap the bottom edge
          child: ElevatedButton.icon(
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Checkin recorded!')),
              );
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.accentOrange,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(30)),
              elevation: 4,
            ),
            icon: const Icon(Icons.access_time_outlined, size: 20),
            label: const Text('Checkin', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          ),
        )
      ],
    );
  }
}
