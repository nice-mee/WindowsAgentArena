<?php
// File: controllers/UserController.php
require_once 'models/User.php';

class UserController {
    public function createUser($name, $email) {
        $user = new User($name, $email);
        // Save the user to a database (simulated)
        echo 'User ' . $user->getName() . ' created successfully';
    }
}
?>
