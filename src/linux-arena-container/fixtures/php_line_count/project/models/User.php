<?php
// File: models/User.php
class User {
    private $name;
    private $email;

    public function __construct($name, $email) {
        $this->name = $name;
        $this->email = $email;
    }

    // Getter and Setter
    public function getName() {
        return $this->name;
    }

    public function getEmail() {
        return $this->email;
    }
}
?>
