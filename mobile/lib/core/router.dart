import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../features/auth/providers/auth_provider.dart';
import '../features/auth/screens/login_screen.dart';
import '../features/main/screens/main_scaffold.dart';
import '../features/home/screens/home_screen.dart';
import '../features/home/screens/tasks_screen.dart';
import '../features/home/screens/events_screen.dart';
import '../features/home/screens/news_screen.dart';
import '../features/attendance/screens/attendance_screen.dart';
import '../features/account/screens/account_screen.dart';

final GlobalKey<NavigatorState> _rootNavigatorKey = GlobalKey<NavigatorState>();
final GlobalKey<NavigatorState> _shellNavigatorHomeKey = GlobalKey<NavigatorState>(debugLabel: 'shellHome');
final GlobalKey<NavigatorState> _shellNavigatorAttendanceKey = GlobalKey<NavigatorState>(debugLabel: 'shellAttendance');
final GlobalKey<NavigatorState> _shellNavigatorAccountKey = GlobalKey<NavigatorState>(debugLabel: 'shellAccount');

final goRouter = GoRouter(
  navigatorKey: _rootNavigatorKey,
  initialLocation: '/login',
  redirect: (context, state) {
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    final isAuth = authProvider.isAuthenticated;
    final isLoggingIn = state.matchedLocation == '/login';

    if (!isAuth && !isLoggingIn) return '/login';
    if (isAuth && isLoggingIn) return '/home';
    return null;
  },
  routes: [
    GoRoute(
      path: '/login',
      builder: (context, state) => const LoginScreen(),
    ),
    StatefulShellRoute.indexedStack(
      builder: (context, state, navigationShell) {
        return MainScaffold(navigationShell: navigationShell);
      },
      branches: [
        StatefulShellBranch(
          navigatorKey: _shellNavigatorHomeKey,
          routes: [
            GoRoute(
              path: '/home',
              builder: (context, state) => const HomeScreen(),
              routes: [
                GoRoute(
                  path: 'tasks',
                  builder: (context, state) => const TasksScreen(),
                ),
                GoRoute(
                  path: 'events',
                  builder: (context, state) => const EventsScreen(),
                ),
                GoRoute(
                  path: 'news',
                  builder: (context, state) => const NewsScreen(),
                ),
              ],
            ),
          ],
        ),
        StatefulShellBranch(
          navigatorKey: _shellNavigatorAttendanceKey,
          routes: [
            GoRoute(
              path: '/attendance',
              builder: (context, state) => const AttendanceScreen(),
            ),
          ],
        ),
        StatefulShellBranch(
          navigatorKey: _shellNavigatorAccountKey,
          routes: [
            GoRoute(
              path: '/account',
              builder: (context, state) => const AccountScreen(),
            ),
          ],
        ),
      ],
    ),
  ],
);
