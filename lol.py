from RobotManipulator import RobotManipulator

def move_robot_by_registers(cobot, dx=0, dy=0, dz=0, program_name="Motion"):
    """Перемещает робота используя регистры и программу."""
    cobot.set_number_register(1, dx)
    cobot.set_number_register(2, dy)
    cobot.set_number_register(3, dz)
    cobot.start_program(program_name)
        
cobot = RobotManipulator("R1", ip="192.168.124.2")
cobot.connect()

move_robot_by_registers(cobot, 175, 280, 200)